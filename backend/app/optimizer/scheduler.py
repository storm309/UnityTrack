"""Google OR-Tools CP-SAT Constraint Optimizer for UnityTrack Maintenance Planning.

This module is completely decoupled from FastAPI and SQLAlchemy.
All inputs and outputs are pure Python dataclasses and primitives.

Mathematical Formulation:
- Hard Constraints:
  1. Task window: earliest_start <= start_time, start_time + duration <= deadline.
  2. Block window confinement: Maintenance blocks strictly inside permissible BlockWindows
     (derived from train timetable gaps, mathematically ensuring ZERO train collisions).
  3. Resource capacity: Concurrent departmental crew in any window <= capacity limit.
  4. Mutual compatibility: Any tasks sharing a block must be pairwise compatible (Section 3).
  5. Block duration coverage: Block duration covers the bundled execution time of its tasks.
  6. Section exclusivity: At most one maintenance block per section per window.
- Multi-Objective Function:
  min w1 * num_blocks + w2 * total_disruption_minutes + w3 * priority_weighted_lateness.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ortools.sat.python import cp_model

from app.optimizer.bundling import (
    BundlingConfig,
    SectionInfo,
    TaskItem,
    check_pairwise_compatibility,
)
from app.optimizer.validator import ScheduledBlock, ScheduledTaskAssignment

logger = logging.getLogger("unitytrack.optimizer.scheduler")


@dataclass
class SchedulerConfig:
    """Configurable weights and runtime parameters for CP-SAT solver."""

    time_limit_seconds: float = 30.0
    random_seed: int = 42
    num_workers: int = 4
    weight_num_blocks: float = 1000.0
    weight_disruption_minutes: float = 5.0
    weight_priority_lateness: float = 1.0
    allow_adjacent_sections: bool = False


@dataclass
class OptimizerPlanResult:
    """Comprehensive output of the CP-SAT maintenance planning optimization."""

    status: str  # OPTIMAL | FEASIBLE | INFEASIBLE | TIMEOUT
    objective_value: Optional[float]
    solve_time_seconds: float
    blocks: List[ScheduledBlock]
    task_assignments: List[ScheduledTaskAssignment]
    total_blocks: int
    total_disruption_minutes: int
    cross_departmental_blocks: int
    tasks_scheduled: int
    infeasible_diagnostics: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


def _diagnose_infeasibility(
    tasks: List[TaskItem],
    candidate_windows: Dict[str, List[Dict[str, Any]]],
    crew_capacities: Dict[str, int],
) -> List[str]:
    """Analyze input tasks and constraints to provide clear actionable diagnostics if infeasible."""
    diagnostics: List[str] = []

    # Check 1: Tasks with 0 feasible candidate windows
    for t in tasks:
        cw = candidate_windows.get(t.id, [])
        if not cw:
            diagnostics.append(
                f"TASK_NO_FEASIBLE_WINDOW: Task '{t.id}' [{t.title}] on section '{t.section_id}' "
                f"(duration {t.duration_min} min, window [{t.earliest_start}, {t.deadline}]) "
                f"has ZERO permissible BlockWindows of sufficient duration in its time horizon."
            )

    # Check 2: Tasks exceeding department capacity
    for t in tasks:
        cap = crew_capacities.get(t.department, 999)
        if t.crew_needed > cap:
            diagnostics.append(
                f"TASK_EXCEEDS_CREW_CAPACITY: Task '{t.id}' requires {t.crew_needed} crew for "
                f"{t.department}, which exceeds maximum concurrent limit of {cap}."
            )

    if not diagnostics:
        diagnostics.append(
            "CONSTRAINT_CONGESTION: High task density and tight deadlines create window contention "
            "or resource capacity bottleneck on one or more corridor sections."
        )

    return diagnostics


def solve_maintenance_schedule(
    tasks: List[TaskItem],
    block_windows: List[Dict[str, Any]],
    crew_capacities: Dict[str, int],
    section_map: Optional[Dict[str, SectionInfo]] = None,
    config: Optional[SchedulerConfig] = None,
) -> OptimizerPlanResult:
    """Formulate and solve the multi-department maintenance scheduling problem with CP-SAT."""
    start_cpu_time = time.perf_counter()
    cfg = config or SchedulerConfig()

    if not tasks:
        return OptimizerPlanResult(
            status="FEASIBLE",
            objective_value=0.0,
            solve_time_seconds=round(time.perf_counter() - start_cpu_time, 3),
            blocks=[],
            task_assignments=[],
            total_blocks=0,
            total_disruption_minutes=0,
            cross_departmental_blocks=0,
            tasks_scheduled=0,
        )

    # 1. Identify Candidate Windows for each Task
    # Each BlockWindow represents a non-overlapping timetable gap on a section.
    candidate_windows: Dict[str, List[Dict[str, Any]]] = {}
    windows_by_id: Dict[str, Dict[str, Any]] = {}

    for w in block_windows:
        w_id = w.get("id", f"{w['section_id']}_{w['start_min']}_{w['end_min']}")
        w["_uid"] = w_id
        windows_by_id[w_id] = w

    for t in tasks:
        c_windows: List[Dict[str, Any]] = []
        for w in block_windows:
            # Geographic match
            if w["section_id"] != t.section_id:
                continue

            # Duration check
            w_dur = w["end_min"] - w["start_min"]
            if w_dur < t.duration_min:
                continue

            # Time overlap check: [max(w_start, E_t), min(w_end, D_t)]
            overlap_start = max(w["start_min"], t.earliest_start)
            overlap_end = min(w["end_min"], t.deadline)

            if (overlap_end - overlap_start) >= t.duration_min:
                c_windows.append(w)

        candidate_windows[t.id] = c_windows

    # Check for immediate infeasibility (tasks with 0 candidate windows)
    unmatchable_tasks = [t for t in tasks if not candidate_windows[t.id]]
    if unmatchable_tasks:
        diag = _diagnose_infeasibility(tasks, candidate_windows, crew_capacities)
        return OptimizerPlanResult(
            status="INFEASIBLE",
            objective_value=None,
            solve_time_seconds=round(time.perf_counter() - start_cpu_time, 3),
            blocks=[],
            task_assignments=[],
            total_blocks=0,
            total_disruption_minutes=0,
            cross_departmental_blocks=0,
            tasks_scheduled=0,
            infeasible_diagnostics=diag,
        )

    # 2. Build CP-SAT Model
    model = cp_model.CpModel()

    # Active windows: only windows that are candidate for at least one task
    active_window_ids: Set[str] = set()
    for cw_list in candidate_windows.values():
        for w in cw_list:
            active_window_ids.add(w["_uid"])

    # Decision Variables:
    # x[t_id, w_id]: boolean indicating task t is assigned to window w
    assign_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
    for t in tasks:
        for w in candidate_windows[t.id]:
            w_id = w["_uid"]
            assign_vars[(t.id, w_id)] = model.new_bool_var(f"x_{t.id}_{w_id}")

    # y[w_id]: boolean indicating block is open in window w
    # b_start[w_id], b_dur[w_id], b_end[w_id]: block timing variables
    block_open: Dict[str, cp_model.IntVar] = {}
    block_start: Dict[str, cp_model.IntVar] = {}
    block_dur: Dict[str, cp_model.IntVar] = {}
    block_end: Dict[str, cp_model.IntVar] = {}

    for w_id in active_window_ids:
        w = windows_by_id[w_id]
        w_dur = w["end_min"] - w["start_min"]

        block_open[w_id] = model.new_bool_var(f"open_{w_id}")
        block_start[w_id] = model.new_int_var(w["start_min"], w["end_min"], f"start_{w_id}")
        block_dur[w_id] = model.new_int_var(0, w_dur, f"dur_{w_id}")
        block_end[w_id] = model.new_int_var(w["start_min"], w["end_min"], f"end_{w_id}")

        # Relation: end = start + dur
        model.add(block_end[w_id] == block_start[w_id] + block_dur[w_id])

        # If block is NOT open, duration must be 0
        model.add(block_dur[w_id] == 0).only_enforce_if(block_open[w_id].negated())

    # Map tasks to active windows
    tasks_by_window: Dict[str, List[TaskItem]] = {}
    for t in tasks:
        for w in candidate_windows[t.id]:
            tasks_by_window.setdefault(w["_uid"], []).append(t)

    # Constraint 1: Every task must be assigned to exactly ONE window
    for t in tasks:
        assigned_in_windows = [
            assign_vars[(t.id, w["_uid"])] for w in candidate_windows[t.id]
        ]
        model.add(sum(assigned_in_windows) == 1)

    # Constraint 2: Link Task Assignment to Block Open
    for w_id, w_tasks in tasks_by_window.items():
        w_assign_vars = [assign_vars[(t.id, w_id)] for t in w_tasks]

        for t in w_tasks:
            # If task is assigned to w, then window w must be open
            model.add(assign_vars[(t.id, w_id)] <= block_open[w_id])

        # If window is open, at least one task must be assigned
        model.add(sum(w_assign_vars) >= block_open[w_id])

    # Constraint 3: Department Crew Resource Capacities per Window
    for w_id, w_tasks in tasks_by_window.items():
        by_dept: Dict[str, List[TaskItem]] = {}
        for t in w_tasks:
            by_dept.setdefault(t.department, []).append(t)

        for dept, d_tasks in by_dept.items():
            cap = crew_capacities.get(dept, 999)
            model.add(
                sum(t.crew_needed * assign_vars[(t.id, w_id)] for t in d_tasks)
                <= cap * block_open[w_id]
            )

    # Constraint 4: Mutual Compatibility Rules (Section 3)
    b_cfg = BundlingConfig(allow_adjacent_sections=cfg.allow_adjacent_sections)
    for w_id, w_tasks in tasks_by_window.items():
        n = len(w_tasks)
        for i in range(n):
            for j in range(i + 1, n):
                t1 = w_tasks[i]
                t2 = w_tasks[j]
                compat = check_pairwise_compatibility(
                    t1,
                    t2,
                    config=b_cfg,
                    section_map=section_map,
                    crew_capacities=crew_capacities,
                )
                if not compat.is_compatible:
                    # They cannot both be assigned to this same window!
                    model.add(
                        assign_vars[(t1.id, w_id)] + assign_vars[(t2.id, w_id)] <= 1
                    )

    # Constraint 5: Block Duration Coverage
    # Parallel between departments, sequential within Engineering
    for w_id, w_tasks in tasks_by_window.items():
        # ENG sequential duration requirement
        eng_tasks = [t for t in w_tasks if t.department == "ENGINEERING"]
        if eng_tasks:
            model.add(
                block_dur[w_id]
                >= sum(t.duration_min * assign_vars[(t.id, w_id)] for t in eng_tasks)
            )

        # TRD and SNT parallel duration requirements
        for t in w_tasks:
            if t.department != "ENGINEERING":
                model.add(block_dur[w_id] >= t.duration_min * assign_vars[(t.id, w_id)])

    # Constraint 6: Task Time Window Constraints
    for w_id, w_tasks in tasks_by_window.items():
        for t in w_tasks:
            var = assign_vars[(t.id, w_id)]
            # Task cannot start before earliest_start
            model.add(block_start[w_id] >= t.earliest_start).only_enforce_if(var)
            # Block must finish before task deadline
            model.add(block_end[w_id] <= t.deadline).only_enforce_if(var)

    # 3. Formulate Multi-Objective Function
    # min w1 * sum(block_open) + w2 * sum(block_dur) + w3 * priority_weighted_lateness
    w1_int = int(round(cfg.weight_num_blocks))
    w2_int = int(round(cfg.weight_disruption_minutes))
    w3_factor = cfg.weight_priority_lateness

    obj_terms: List[Any] = []

    # Term 1: Number of blocks
    if w1_int > 0:
        obj_terms.append(w1_int * sum(block_open[w_id] for w_id in active_window_ids))

    # Term 2: Total disruption minutes
    if w2_int > 0:
        obj_terms.append(w2_int * sum(block_dur[w_id] for w_id in active_window_ids))

    # Term 3: Priority-weighted scheduling time (earlier is better for high-priority tasks)
    if w3_factor > 0:
        for t in tasks:
            p_weight = max(1, int(round(t.priority_score)))
            for w in candidate_windows[t.id]:
                w_id = w["_uid"]
                # Start hour scaled by priority weight
                window_hour = w["start_min"] // 60
                coef = int(round(w3_factor * p_weight * window_hour))
                if coef > 0:
                    obj_terms.append(coef * assign_vars[(t.id, w_id)])

    model.minimize(sum(obj_terms))

    # 4. Configure and Run CP-SAT Solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.time_limit_seconds
    solver.parameters.random_seed = cfg.random_seed
    solver.parameters.num_workers = cfg.num_workers
    solver.parameters.log_search_progress = False

    status_code = solver.solve(model)
    solve_duration = round(time.perf_counter() - start_cpu_time, 3)

    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        status_name = "INFEASIBLE" if status_code == cp_model.INFEASIBLE else "TIMEOUT"
        diag = _diagnose_infeasibility(tasks, candidate_windows, crew_capacities)
        return OptimizerPlanResult(
            status=status_name,
            objective_value=None,
            solve_time_seconds=solve_duration,
            blocks=[],
            task_assignments=[],
            total_blocks=0,
            total_disruption_minutes=0,
            cross_departmental_blocks=0,
            tasks_scheduled=0,
            infeasible_diagnostics=diag,
        )

    status_str = "OPTIMAL" if status_code == cp_model.OPTIMAL else "FEASIBLE"
    obj_val = float(solver.objective_value)

    # 5. Extract Scheduled Blocks and Task Assignments
    scheduled_blocks: List[ScheduledBlock] = []
    task_assignments: List[ScheduledTaskAssignment] = []
    block_counter = 1

    for w_id in sorted(active_window_ids):
        if solver.value(block_open[w_id]) == 1:
            w = windows_by_id[w_id]
            b_st = int(solver.value(block_start[w_id]))
            b_d = int(solver.value(block_dur[w_id]))
            b_en = b_st + b_d

            # Collect assigned tasks
            b_tasks: List[TaskItem] = []
            for t in tasks_by_window[w_id]:
                if solver.value(assign_vars[(t.id, w_id)]) == 1:
                    b_tasks.append(t)

            if not b_tasks:
                continue

            # Sort tasks deterministically
            b_tasks.sort(key=lambda x: x.id)
            task_ids = [t.id for t in b_tasks]
            depts = sorted(list({t.department for t in b_tasks}))
            has_power_off = any(t.requires_power_off for t in b_tasks)
            has_track_block = any(t.requires_track_block for t in b_tasks)

            block_id = f"OPT-BLK-{block_counter:03d}"
            block_counter += 1

            new_block = ScheduledBlock(
                block_id=block_id,
                section_id=w["section_id"],
                start_min=b_st,
                end_min=b_en,
                duration_min=b_d,
                task_ids=task_ids,
                departments=depts,
                requires_power_off=has_power_off,
                requires_track_block=has_track_block,
            )
            scheduled_blocks.append(new_block)

            # Record per-task assignments
            curr_eng_offset = b_st
            for t in b_tasks:
                if t.department == "ENGINEERING":
                    t_start = curr_eng_offset
                    curr_eng_offset += t.duration_min
                else:
                    t_start = b_st

                t_finish = t_start + t.duration_min
                is_del = t_finish > t.deadline
                del_min = max(0, t_finish - t.deadline)

                task_assignments.append(
                    ScheduledTaskAssignment(
                        task_id=t.id,
                        block_id=block_id,
                        section_id=w["section_id"],
                        start_min=t_start,
                        duration_min=t.duration_min,
                        finish_min=t_finish,
                        department=t.department,
                        is_delayed=is_del,
                        delay_minutes=del_min,
                    )
                )

    # Sort blocks chronologically
    scheduled_blocks.sort(key=lambda b: (b.start_min, b.section_id))
    cross_dept_blocks = sum(1 for b in scheduled_blocks if len(b.departments) > 1)
    tot_disruption = sum(b.duration_min for b in scheduled_blocks)

    return OptimizerPlanResult(
        status=status_str,
        objective_value=obj_val,
        solve_time_seconds=solve_duration,
        blocks=scheduled_blocks,
        task_assignments=task_assignments,
        total_blocks=len(scheduled_blocks),
        total_disruption_minutes=tot_disruption,
        cross_departmental_blocks=cross_dept_blocks,
        tasks_scheduled=len(task_assignments),
        stats={
            "num_variables": len(assign_vars) + len(active_window_ids) * 4,
            "active_windows": len(active_window_ids),
            "wall_time": solve_duration,
        },
    )
