"""Pure Python What-If Scenario Simulator and Multi-Scenario Comparison Engine.

This module is completely decoupled from FastAPI and SQLAlchemy.
All inputs, outputs, and intermediate states are pure Python dataclasses and primitives.

Key Guarantees:
1. Base data immutability: Original base tasks, block windows, train slots, and capacities
   are NEVER mutated. All scenarios operate on deep-copied overlays.
2. Comprehensive parameter support:
   - Add emergency / unscheduled tasks.
   - Restrict or close sections over specified time intervals.
   - Override task deadlines.
   - Override departmental crew capacity per window.
   - Override solver objective weights.
   - Add special train slots or remove existing train slots.
3. Multi-scenario comparative evaluation:
   - Evaluates 2-4 scenarios side-by-side.
   - Computes composite penalty score and ranks candidates.
   - Generates plain-language justification derived strictly from solver metrics.
"""

from __future__ import annotations

import copy
import dataclasses
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.optimizer.bundling import TaskItem
from app.optimizer.scheduler import (
    OptimizerPlanResult,
    SchedulerConfig,
    solve_maintenance_schedule,
)
from app.optimizer.validator import (
    ScheduledBlock,
    ScheduledTaskAssignment,
    ValidationResult,
    validate_schedule,
)

logger = logging.getLogger("unitytrack.optimizer.scenario")


@dataclass
class ScenarioOverlayData:
    """In-memory overlay definition containing all modifications to base data."""

    name: str = "Scenario"
    add_tasks: List[TaskItem] = field(default_factory=list)
    restrict_sections: List[Dict[str, Any]] = field(default_factory=list)
    deadline_overrides: Dict[str, int] = field(default_factory=dict)
    capacity_overrides: Dict[str, int] = field(default_factory=dict)
    weight_overrides: Dict[str, float] = field(default_factory=dict)
    add_train_slots: List[Dict[str, Any]] = field(default_factory=list)
    remove_train_slot_ids: List[str] = field(default_factory=list)
    allow_adjacent_sections: bool = False


@dataclass
class DelayedTaskItem:
    """Details of a task that is delayed in a scenario schedule."""

    task_id: str
    department: str
    title: str
    priority_score: float
    deadline: int
    finish_min: int
    delay_minutes: int
    is_high_priority: bool


@dataclass
class ScenarioSimulationResult:
    """Complete outcome of a simulated scenario."""

    name: str
    status: str  # OPTIMAL | FEASIBLE | INFEASIBLE | TIMEOUT
    objective_value: Optional[float]
    solve_time_seconds: float
    total_blocks: int
    total_disruption_minutes: int
    cross_departmental_blocks: int
    tasks_scheduled: int
    total_tasks_count: int
    delayed_tasks: int
    high_priority_delays: int
    total_delay_minutes: int
    delayed_task_details: List[DelayedTaskItem]
    composite_penalty_score: float
    blocks: List[ScheduledBlock]
    task_assignments: List[ScheduledTaskAssignment]
    validation: Optional[ValidationResult] = None
    infeasible_diagnostics: Optional[List[str]] = None


@dataclass
class ScenarioRankedComparison:
    """Evaluation summary for a single scenario candidate in a comparison."""

    name: str
    status: str
    total_blocks: int
    total_disruption_minutes: int
    cross_departmental_blocks: int
    delayed_tasks: int
    high_priority_delays: int
    total_delay_minutes: int
    solve_time_seconds: float
    composite_penalty_score: float
    rank: int
    is_best: bool
    evaluation_notes: str


@dataclass
class ScenarioComparisonOutcome:
    """Full side-by-side comparison of 2-4 scenarios."""

    scenarios_evaluated: int
    ranking_rule: str
    best_scenario_name: str
    best_scenario_reason: str
    ranked_scenarios: List[ScenarioRankedComparison]
    scenario_results: Dict[str, ScenarioSimulationResult]
    delta_vs_reference: Optional[Dict[str, Any]] = None


def apply_scenario_overlay(
    base_tasks: List[TaskItem],
    base_windows: List[Dict[str, Any]],
    base_train_slots: List[Dict[str, Any]],
    base_capacities: Dict[str, int],
    overlay: ScenarioOverlayData,
    base_config: Optional[SchedulerConfig] = None,
) -> Tuple[
    List[TaskItem],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    Dict[str, int],
    SchedulerConfig,
]:
    """Apply overlay modifications to base inputs, returning modified copies without mutating originals.

    Guarantees:
    - Zero mutation to base_tasks, base_windows, base_train_slots, base_capacities.
    - Deep-copied, safely transformed scenario data.
    """
    # 1. Clone tasks and apply deadline overrides
    scenario_tasks: List[TaskItem] = []
    for t in base_tasks:
        if t.id in overlay.deadline_overrides:
            scenario_tasks.append(dataclasses.replace(t, deadline=overlay.deadline_overrides[t.id]))
        else:
            scenario_tasks.append(t)

    # Add emergency tasks
    for new_t in overlay.add_tasks:
        scenario_tasks.append(copy.deepcopy(new_t))

    # 2. Clone capacities and apply overrides
    scenario_capacities: Dict[str, int] = dict(base_capacities)
    for dept, cap in overlay.capacity_overrides.items():
        scenario_capacities[dept] = cap

    # 3. Clone train slots and apply additions/removals
    removed_set = set(overlay.remove_train_slot_ids)
    scenario_train_slots: List[Dict[str, Any]] = [
        copy.deepcopy(ts) for ts in base_train_slots if ts["id"] not in removed_set
    ]
    for new_ts in overlay.add_train_slots:
        scenario_train_slots.append(copy.deepcopy(new_ts))

    # 4. Filter and truncate block windows based on train slots and section restrictions
    # Start with base windows
    candidate_windows: List[Dict[str, Any]] = [
        copy.deepcopy(w) for w in base_windows
    ]

    # A. If train slots were added, eliminate windows that collide with new train slots
    if overlay.add_train_slots:
        filtered_windows: List[Dict[str, Any]] = []
        for w in candidate_windows:
            w_sec = w["section_id"]
            w_st = w["start_min"]
            w_en = w["end_min"]

            # Check collision with any added train slot on this section
            collision = False
            for ts in overlay.add_train_slots:
                if ts.get("section_id") == w_sec:
                    ts_st = ts["start_min"]
                    ts_en = ts["end_min"]
                    # Collision if intervals overlap
                    if not (w_en <= ts_st or w_st >= ts_en):
                        collision = True
                        break

            if not collision:
                filtered_windows.append(w)
        candidate_windows = filtered_windows

    # B. Apply section restrictions (closures or maintenance bans)
    if overlay.restrict_sections:
        restricted_windows: List[Dict[str, Any]] = []
        for w in candidate_windows:
            w_sec = w["section_id"]
            w_st = w["start_min"]
            w_en = w["end_min"]

            is_eliminated = False
            curr_st = w_st
            curr_en = w_en

            for restr in overlay.restrict_sections:
                if restr.get("section_id") == w_sec:
                    r_st = restr["start_min"]
                    r_en = restr["end_min"]

                    # Check overlap with restriction
                    if not (curr_en <= r_st or curr_st >= r_en):
                        # Fully covered by restriction -> eliminate
                        if r_st <= curr_st and r_en >= curr_en:
                            is_eliminated = True
                            break
                        # Partially overlaps: truncate if possible
                        if curr_st < r_st and curr_en > r_en:
                            # Split or pick larger segment; pick pre-restriction segment
                            curr_en = r_st
                        elif curr_st < r_st:
                            curr_en = r_st
                        elif curr_en > r_en:
                            curr_st = r_en

            if not is_eliminated and (curr_en - curr_st) >= 60:
                new_w = dict(w)
                new_w["start_min"] = curr_st
                new_w["end_min"] = curr_en
                new_w["duration_min"] = curr_en - curr_st
                restricted_windows.append(new_w)

        candidate_windows = restricted_windows

    # 5. Build SchedulerConfig with weight overrides
    cfg = copy.deepcopy(base_config) if base_config else SchedulerConfig()
    if "weight_num_blocks" in overlay.weight_overrides:
        cfg.weight_num_blocks = overlay.weight_overrides["weight_num_blocks"]
    if "weight_disruption_minutes" in overlay.weight_overrides:
        cfg.weight_disruption_minutes = overlay.weight_overrides["weight_disruption_minutes"]
    if "weight_priority_lateness" in overlay.weight_overrides:
        cfg.weight_priority_lateness = overlay.weight_overrides["weight_priority_lateness"]
    cfg.allow_adjacent_sections = overlay.allow_adjacent_sections

    return (
        scenario_tasks,
        candidate_windows,
        scenario_train_slots,
        scenario_capacities,
        cfg,
    )


def compute_composite_penalty_score(
    status: str,
    total_blocks: int,
    total_disruption_minutes: int,
    delayed_tasks: int,
    high_priority_delays: int,
    solve_time_seconds: float = 0.0,
) -> float:
    """Calculate the standardized multi-criteria penalty score for scenario ranking.

    Documented Rule:
    - Infeasible / Timeout status penalty: 10,000 points.
    - High-priority delay penalty: 5,000 points per task.
    - Total delay penalty: 1,000 points per task.
    - Block count penalty: 100 points per block.
    - Disruption penalty: 1 point per disruption minute.
    - Solve time tie-breaker: 0.1 point per second.

    Lower score is strictly better.
    """
    score = 0.0
    if status not in ("OPTIMAL", "FEASIBLE"):
        score += 10000.0

    score += high_priority_delays * 5000.0
    score += delayed_tasks * 1000.0
    score += total_blocks * 100.0
    score += total_disruption_minutes * 1.0
    score += solve_time_seconds * 0.1

    return round(score, 2)


def run_scenario_simulation(
    base_tasks: List[TaskItem],
    base_windows: List[Dict[str, Any]],
    base_train_slots: List[Dict[str, Any]],
    base_capacities: Dict[str, int],
    overlay: ScenarioOverlayData,
    base_config: Optional[SchedulerConfig] = None,
    time_limit_seconds: float = 15.0,
) -> ScenarioSimulationResult:
    """Execute a single what-if scenario simulation on top of base railway data."""
    # 1. Apply overlay without mutating base data
    (
        scen_tasks,
        scen_windows,
        scen_trains,
        scen_capacities,
        scen_cfg,
    ) = apply_scenario_overlay(
        base_tasks,
        base_windows,
        base_train_slots,
        base_capacities,
        overlay,
        base_config=base_config,
    )
    scen_cfg.time_limit_seconds = time_limit_seconds

    # 2. Solve maintenance schedule
    opt_res: OptimizerPlanResult = solve_maintenance_schedule(
        tasks=scen_tasks,
        block_windows=scen_windows,
        crew_capacities=scen_capacities,
        config=scen_cfg,
    )

    # 3. Analyze delays and diagnostics
    task_map = {t.id: t for t in scen_tasks}
    delayed_details: List[DelayedTaskItem] = []
    high_priority_delays_count = 0
    total_delay_min = 0

    if opt_res.status in ("OPTIMAL", "FEASIBLE"):
        for a in opt_res.task_assignments:
            if a.is_delayed:
                t = task_map.get(a.task_id)
                p_score = t.priority_score if t else 50.0
                crit = t.criticality if t else 3
                is_high = p_score >= 80.0 or crit >= 4
                if is_high:
                    high_priority_delays_count += 1
                total_delay_min += a.delay_minutes

                delayed_details.append(
                    DelayedTaskItem(
                        task_id=a.task_id,
                        department=a.department,
                        title=t.title if t else f"Task {a.task_id}",
                        priority_score=round(p_score, 1),
                        deadline=t.deadline if t else a.finish_min,
                        finish_min=a.finish_min,
                        delay_minutes=a.delay_minutes,
                        is_high_priority=is_high,
                    )
                )

        # 4. Independent Validation
        val_res = validate_schedule(
            blocks=opt_res.blocks,
            tasks=task_map,
            train_slots=scen_trains,
            block_windows=scen_windows,
            crew_capacities=scen_capacities,
            require_all_tasks_scheduled=True,
            expected_task_ids=set(task_map.keys()),
        )
    else:
        val_res = None

    penalty = compute_composite_penalty_score(
        status=opt_res.status,
        total_blocks=opt_res.total_blocks,
        total_disruption_minutes=opt_res.total_disruption_minutes,
        delayed_tasks=len(delayed_details),
        high_priority_delays=high_priority_delays_count,
        solve_time_seconds=opt_res.solve_time_seconds,
    )

    return ScenarioSimulationResult(
        name=overlay.name,
        status=opt_res.status,
        objective_value=opt_res.objective_value,
        solve_time_seconds=opt_res.solve_time_seconds,
        total_blocks=opt_res.total_blocks,
        total_disruption_minutes=opt_res.total_disruption_minutes,
        cross_departmental_blocks=opt_res.cross_departmental_blocks,
        tasks_scheduled=opt_res.tasks_scheduled,
        total_tasks_count=len(scen_tasks),
        delayed_tasks=len(delayed_details),
        high_priority_delays=high_priority_delays_count,
        total_delay_minutes=total_delay_min,
        delayed_task_details=delayed_details,
        composite_penalty_score=penalty,
        blocks=opt_res.blocks,
        task_assignments=opt_res.task_assignments,
        validation=val_res,
        infeasible_diagnostics=opt_res.infeasible_diagnostics,
    )


def compare_scenario_simulations(
    scenarios: List[ScenarioSimulationResult],
    reference_result: Optional[ScenarioSimulationResult] = None,
) -> ScenarioComparisonOutcome:
    """Compare 2-4 scenarios side-by-side and designate the best by documented penalty rule."""
    if not scenarios:
        raise ValueError("At least one scenario must be provided for comparison.")

    # Sort scenarios by composite penalty score ascending
    sorted_scenarios = sorted(
        scenarios,
        key=lambda s: (
            0 if s.status in ("OPTIMAL", "FEASIBLE") else 1,
            s.composite_penalty_score,
            s.high_priority_delays,
            s.delayed_tasks,
            s.total_blocks,
            s.total_disruption_minutes,
        ),
    )

    best_scen = sorted_scenarios[0]

    # Generate plain-language reason strictly based on solver numbers
    if best_scen.status not in ("OPTIMAL", "FEASIBLE"):
        best_reason = f"All evaluated scenarios were {best_scen.status}."
    else:
        best_reason = (
            f"Scenario '{best_scen.name}' achieved the best balance: "
            f"status {best_scen.status}, {best_scen.total_blocks} total maintenance blocks, "
            f"{best_scen.total_disruption_minutes} disruption minutes, and "
            f"{best_scen.delayed_tasks} delayed tasks ({best_scen.high_priority_delays} high priority)."
        )

    ranking_rule_str = (
        "Multi-criteria penalty evaluation: Infeasible/Timeout (+10000), High-priority delays "
        "(+5000/task), Total delays (+1000/task), Total blocks (+100/block), Disruption minutes (+1/min)."
    )

    ranked_items: List[ScenarioRankedComparison] = []
    scen_dict: Dict[str, ScenarioSimulationResult] = {}

    for idx, s in enumerate(sorted_scenarios, start=1):
        is_winner = (idx == 1 and s.status in ("OPTIMAL", "FEASIBLE"))
        notes = (
            f"Rank {idx}: {s.status}. Blocks: {s.total_blocks}, Disruption: {s.total_disruption_minutes}m, "
            f"Delays: {s.delayed_tasks} ({s.high_priority_delays} critical). Penalty: {s.composite_penalty_score}."
        )
        ranked_items.append(
            ScenarioRankedComparison(
                name=s.name,
                status=s.status,
                total_blocks=s.total_blocks,
                total_disruption_minutes=s.total_disruption_minutes,
                cross_departmental_blocks=s.cross_departmental_blocks,
                delayed_tasks=s.delayed_tasks,
                high_priority_delays=s.high_priority_delays,
                total_delay_minutes=s.total_delay_minutes,
                solve_time_seconds=s.solve_time_seconds,
                composite_penalty_score=s.composite_penalty_score,
                rank=idx,
                is_best=is_winner,
                evaluation_notes=notes,
            )
        )
        scen_dict[s.name] = s

    # Compute deltas vs reference scenario if provided
    deltas: Optional[Dict[str, Any]] = None
    if reference_result:
        deltas = {}
        for s in scenarios:
            deltas[s.name] = {
                "delta_blocks": s.total_blocks - reference_result.total_blocks,
                "delta_disruption_minutes": s.total_disruption_minutes - reference_result.total_disruption_minutes,
                "delta_delayed_tasks": s.delayed_tasks - reference_result.delayed_tasks,
                "delta_high_priority_delays": s.high_priority_delays - reference_result.high_priority_delays,
                "delta_solve_time": round(s.solve_time_seconds - reference_result.solve_time_seconds, 3),
            }

    return ScenarioComparisonOutcome(
        scenarios_evaluated=len(scenarios),
        ranking_rule=ranking_rule_str,
        best_scenario_name=best_scen.name,
        best_scenario_reason=best_reason,
        ranked_scenarios=ranked_items,
        scenario_results=scen_dict,
        delta_vs_reference=deltas,
    )
