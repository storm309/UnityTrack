"""Pure Python compatibility matrix and multi-department bundling engine for UnityTrack.

This module is strictly decoupled from FastAPI and SQLAlchemy.
All inputs and outputs are pure Python dataclasses / primitives.

Indian Railways Maintenance Bundling Rules:
1. Geographic: Same corridor; same physical track section (or adjacent if configured).
2. Temporal: Feasible windows [earliest_start, deadline] must have non-empty overlap
   at least as long as the bundled duration.
3. Department & Safety Matrix:
   - SNT + TRACTION: Fully compatible. SNT inspects track circuits/points during OHE power-off (PARALLEL).
   - ENGINEERING + SNT: Compatible. Heavy track machine operations vs track circuit testing run SEQUENTIAL;
     inspection/renewal tasks run PARALLEL.
   - ENGINEERING + TRACTION: Compatible when power-off is enforced (PARALLEL).
     Live-line traction work during heavy track block is strictly prohibited.
   - Same-Department:
     - ENG + ENG: Track machines move sequentially along single track (SEQUENTIAL).
     - TRD + TRD: Parallel if distinct assets (insulators vs cantilevers), sequential if same wire span.
     - SNT + SNT: Parallel across distinct signaling gear (points vs signals).
4. Resource Capacity: Combined crew per department must not exceed the department's
   capacity limit per maintenance window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class TaskItem:
    """Minimal representation of a maintenance task for bundling."""

    id: str
    title: str
    department: str  # ENGINEERING | TRACTION | SNT
    section_id: str
    corridor_id: str
    asset_type: str
    duration_min: int
    earliest_start: int
    deadline: int
    crew_needed: int
    requires_power_off: bool = False
    requires_track_block: bool = True
    criticality: int = 3
    defect_severity: int = 3
    priority_score: float = 0.0


@dataclass(frozen=True)
class SectionInfo:
    """Track section metadata for geographic adjacency checks."""

    id: str
    corridor_id: str
    name: str
    order_index: int


@dataclass
class BundlingConfig:
    """Configuration options for compatibility and bundle candidate search."""

    allow_adjacent_sections: bool = False
    max_bundle_size: int = 3
    default_crew_capacities: Dict[str, int] = field(
        default_factory=lambda: {
            "ENGINEERING": 3,
            "TRACTION": 2,
            "SNT": 3,
        }
    )


@dataclass
class CompatibilityResult:
    """Outcome of a pairwise task compatibility check."""

    is_compatible: bool
    conflict_code: Optional[str] = None
    conflict_reason: Optional[str] = None
    execution_mode: str = "PARALLEL"  # PARALLEL | SEQUENTIAL
    combined_duration_min: int = 0
    disruption_savings_min: int = 0
    requires_power_off: bool = False
    requires_track_block: bool = True
    reasons: List[str] = field(default_factory=list)


@dataclass
class BundleCandidate:
    """Candidate bundle of mutually compatible maintenance tasks."""

    bundle_id: str
    task_ids: List[str]
    section_id: str
    corridor_id: str
    departments: List[str]
    is_cross_departmental: bool
    execution_mode: str  # PARALLEL | SEQUENTIAL | HYBRID
    duration_min: int
    disruption_savings_min: int
    efficiency_gain_pct: float
    earliest_start: int
    deadline: int
    feasibility_window_min: int
    requires_power_off: bool
    requires_track_block: bool
    crew_needed_by_dept: Dict[str, int]
    combined_priority_score: float
    compatibility_reasons: List[str]
    tasks_summary: List[Dict[str, Any]]


# Conflict code constants
CONFLICT_CORRIDOR_MISMATCH = "CORRIDOR_MISMATCH"
CONFLICT_SECTION_MISMATCH = "SECTION_MISMATCH"
CONFLICT_SECTION_NOT_ADJACENT = "SECTION_NOT_ADJACENT"
CONFLICT_WINDOW_DISJOINT = "WINDOW_DISJOINT"
CONFLICT_WINDOW_TOO_SHORT = "WINDOW_TOO_SHORT"
CONFLICT_CREW_CAPACITY_EXCEEDED = "CREW_CAPACITY_EXCEEDED"
CONFLICT_SAFETY_LIVE_LINE = "SAFETY_CONFLICT_LIVE_LINE"


def check_pairwise_compatibility(
    task_a: TaskItem,
    task_b: TaskItem,
    config: Optional[BundlingConfig] = None,
    section_map: Optional[Dict[str, SectionInfo]] = None,
    crew_capacities: Optional[Dict[str, int]] = None,
) -> CompatibilityResult:
    """Evaluate whether two tasks can be bundled into the same maintenance block."""
    cfg = config or BundlingConfig()
    capacities = crew_capacities or cfg.default_crew_capacities
    reasons: List[str] = []

    # 1. Geographic Check: Corridor
    if task_a.corridor_id != task_b.corridor_id:
        return CompatibilityResult(
            is_compatible=False,
            conflict_code=CONFLICT_CORRIDOR_MISMATCH,
            conflict_reason=(
                f"Tasks belong to different corridors: '{task_a.corridor_id}' vs '{task_b.corridor_id}'"
            ),
        )

    # 2. Geographic Check: Section
    if task_a.section_id != task_b.section_id:
        if not cfg.allow_adjacent_sections:
            return CompatibilityResult(
                is_compatible=False,
                conflict_code=CONFLICT_SECTION_MISMATCH,
                conflict_reason=(
                    f"Tasks are on different sections: '{task_a.section_id}' vs '{task_b.section_id}' "
                    f"(adjacent bundling disabled)"
                ),
            )
        # Check adjacency if enabled
        if section_map and task_a.section_id in section_map and task_b.section_id in section_map:
            sec_a = section_map[task_a.section_id]
            sec_b = section_map[task_b.section_id]
            if abs(sec_a.order_index - sec_b.order_index) > 1:
                return CompatibilityResult(
                    is_compatible=False,
                    conflict_code=CONFLICT_SECTION_NOT_ADJACENT,
                    conflict_reason=(
                        f"Sections '{task_a.section_id}' and '{task_b.section_id}' are not adjacent "
                        f"(orders: {sec_a.order_index} and {sec_b.order_index})"
                    ),
                )
            reasons.append(
                f"Adjacent sections '{task_a.section_id}' and '{task_b.section_id}' eligible for corridor bundle"
            )
        else:
            return CompatibilityResult(
                is_compatible=False,
                conflict_code=CONFLICT_SECTION_MISMATCH,
                conflict_reason=f"Section metadata unavailable to verify adjacency for '{task_a.section_id}' and '{task_b.section_id}'",
            )
    else:
        reasons.append(f"Same physical track section '{task_a.section_id}'")

    # 3. Department & Safety Matrix: Determine Execution Mode & Safety Requirements
    dept_a = task_a.department.upper()
    dept_b = task_b.department.upper()
    requires_power_off = task_a.requires_power_off or task_b.requires_power_off
    requires_track_block = task_a.requires_track_block or task_b.requires_track_block

    # Determine execution mode: PARALLEL or SEQUENTIAL
    if dept_a != dept_b:
        # Cross-departmental pairing
        dept_pair = {dept_a, dept_b}

        if dept_pair == {"TRACTION", "SNT"}:
            execution_mode = "PARALLEL"
            reasons.append("S&T inspection safely rides inside TRD power-off window in parallel")

        elif dept_pair == {"ENGINEERING", "TRACTION"}:
            # Safety check: Live-line traction work cannot happen alongside heavy track machinery
            # If TRD doesn't take power-off but ENG has track block with machines
            if not task_b.requires_power_off and not task_a.requires_power_off:
                # Live-line work without power block during heavy track possession
                return CompatibilityResult(
                    is_compatible=False,
                    conflict_code=CONFLICT_SAFETY_LIVE_LINE,
                    conflict_reason=(
                        "Safety violation: Live-traction work is prohibited during heavy track block without power-off"
                    ),
                )
            execution_mode = "PARALLEL"
            requires_power_off = True  # Power-off enforced for safety of civil crew under OHE
            reasons.append("Coordinated OHE power-off allows parallel track civil works with safe earthing")

        elif dept_pair == {"ENGINEERING", "SNT"}:
            # Check for physical track machine vs track circuit lead interference
            is_heavy_track_machine = any(
                keyword in task_a.asset_type.lower() or keyword in task_a.title.lower()
                for keyword in ["tamping", "grinding", "ballast", "renewal"]
            )
            is_track_circuit = "circuit" in task_b.asset_type.lower() or "circuit" in task_b.title.lower()

            if is_heavy_track_machine and is_track_circuit:
                execution_mode = "SEQUENTIAL"
                reasons.append(
                    "Heavy track machine and track circuit testing must run sequentially to avoid sensor damage"
                )
            else:
                execution_mode = "PARALLEL"
                reasons.append("Civil track maintenance and S&T signaling work operate in parallel")

        else:
            execution_mode = "PARALLEL"
            reasons.append(f"Cross-departmental parallel execution ({dept_a} + {dept_b})")

    else:
        # Same-department pairing
        if dept_a == "ENGINEERING":
            # Track machines and civil gangs on the same track section must run sequentially
            execution_mode = "SEQUENTIAL"
            reasons.append("Same-department civil operations execute sequentially along the track")

        elif dept_a == "TRACTION":
            # If distinct assets (e.g. Insulator washing vs Cantilever), can work in parallel
            if task_a.asset_type != task_b.asset_type:
                execution_mode = "PARALLEL"
                reasons.append(
                    f"Traction teams work in parallel on distinct OHE assets ({task_a.asset_type} and {task_b.asset_type})"
                )
            else:
                execution_mode = "SEQUENTIAL"
                reasons.append(f"Sequential OHE work on identical asset type ({task_a.asset_type})")

        elif dept_a == "SNT":
            # If distinct signaling equipment, parallel
            if task_a.asset_type != task_b.asset_type:
                execution_mode = "PARALLEL"
                reasons.append(
                    f"S&T teams work in parallel on distinct equipment ({task_a.asset_type} and {task_b.asset_type})"
                )
            else:
                execution_mode = "SEQUENTIAL"
                reasons.append(f"Sequential S&T work on identical asset type ({task_a.asset_type})")

        else:
            execution_mode = "SEQUENTIAL"
            reasons.append("Same-department tasks execute sequentially")

    # 4. Compute Duration & Disruption Savings
    if execution_mode == "PARALLEL":
        combined_duration = max(task_a.duration_min, task_b.duration_min)
        disruption_savings = (task_a.duration_min + task_b.duration_min) - combined_duration
        reasons.append(
            f"Parallel execution duration = max({task_a.duration_min}, {task_b.duration_min}) = {combined_duration} min"
        )
    else:
        combined_duration = task_a.duration_min + task_b.duration_min
        disruption_savings = 0  # Sequential takes sum of times, but saves 1 separate block mobilization
        reasons.append(
            f"Sequential execution duration = {task_a.duration_min} + {task_b.duration_min} = {combined_duration} min"
        )

    # 5. Temporal Check: Feasible Overlap Window
    overlap_start = max(task_a.earliest_start, task_b.earliest_start)
    overlap_deadline = min(task_a.deadline, task_b.deadline)

    if overlap_start >= overlap_deadline:
        return CompatibilityResult(
            is_compatible=False,
            conflict_code=CONFLICT_WINDOW_DISJOINT,
            conflict_reason=(
                f"Feasible execution windows [{task_a.earliest_start}, {task_a.deadline}] and "
                f"[{task_b.earliest_start}, {task_b.deadline}] do not overlap"
            ),
        )

    available_overlap = overlap_deadline - overlap_start
    if available_overlap < combined_duration:
        return CompatibilityResult(
            is_compatible=False,
            conflict_code=CONFLICT_WINDOW_TOO_SHORT,
            conflict_reason=(
                f"Feasible overlap window of {available_overlap} min is insufficient for required "
                f"{execution_mode.lower()} duration of {combined_duration} min"
            ),
        )

    reasons.append(
        f"Common feasible window [{overlap_start}, {overlap_deadline}] ({available_overlap} min) "
        f"fits required {combined_duration} min"
    )

    # 6. Resource Capacity Check
    crew_by_dept: Dict[str, int] = {}
    for t in (task_a, task_b):
        crew_by_dept[t.department] = crew_by_dept.get(t.department, 0) + t.crew_needed

    for dept, needed in crew_by_dept.items():
        limit = capacities.get(dept, 999)
        if needed > limit:
            return CompatibilityResult(
                is_compatible=False,
                conflict_code=CONFLICT_CREW_CAPACITY_EXCEEDED,
                conflict_reason=(
                    f"Department '{dept}' combined crew requirement of {needed} exceeds "
                    f"concurrent capacity limit of {limit}"
                ),
            )

    reasons.append("Combined departmental crew requirements are within concurrent capacity limits")

    return CompatibilityResult(
        is_compatible=True,
        execution_mode=execution_mode,
        combined_duration_min=combined_duration,
        disruption_savings_min=disruption_savings,
        requires_power_off=requires_power_off,
        requires_track_block=requires_track_block,
        reasons=reasons,
    )


def compute_bundle_metrics(
    tasks: List[TaskItem],
    config: Optional[BundlingConfig] = None,
) -> Tuple[int, str, int, float, bool, bool, Dict[str, int]]:
    """Compute aggregate duration, execution mode, disruption savings, and resource needs for a bundle.

    Aggregation Rule:
    - Group tasks by department.
    - Within each department: if same-department sequential, sum durations; if parallel, max duration.
    - Across departments: cross-departmental operations execute in PARALLEL.
      Overall duration = max(department_durations).
    - If all tasks in bundle are parallel, mode is "PARALLEL".
    - If all tasks in bundle are sequential, mode is "SEQUENTIAL".
    - Otherwise, mode is "HYBRID".
    """
    _ = config or BundlingConfig()

    dept_groups: Dict[str, List[TaskItem]] = {}
    crew_by_dept: Dict[str, int] = {}
    requires_power_off = any(t.requires_power_off for t in tasks)
    requires_track_block = any(t.requires_track_block for t in tasks)

    total_sum_durations = sum(t.duration_min for t in tasks)

    for t in tasks:
        dept_groups.setdefault(t.department, []).append(t)
        crew_by_dept[t.department] = crew_by_dept.get(t.department, 0) + t.crew_needed

    dept_durations: Dict[str, int] = {}
    has_sequential = False
    has_parallel = False

    for dept, d_tasks in dept_groups.items():
        if len(d_tasks) == 1:
            dept_durations[dept] = d_tasks[0].duration_min
        else:
            # Check internal department execution
            if dept == "ENGINEERING":
                # ENG tasks on same section execute sequentially
                dept_durations[dept] = sum(t.duration_min for t in d_tasks)
                has_sequential = True
            else:
                # TRD or SNT: parallel if different asset types, sequential if same
                asset_types = {t.asset_type for t in d_tasks}
                if len(asset_types) == len(d_tasks):
                    dept_durations[dept] = max(t.duration_min for t in d_tasks)
                    has_parallel = True
                else:
                    dept_durations[dept] = sum(t.duration_min for t in d_tasks)
                    has_sequential = True

    # Cross-departmental coordination runs concurrently in the same block window
    if len(dept_groups) > 1:
        has_parallel = True
        bundle_duration = max(dept_durations.values())
    else:
        bundle_duration = next(iter(dept_durations.values()))

    # Determine execution mode label
    if has_sequential and has_parallel:
        execution_mode = "HYBRID"
    elif has_sequential:
        execution_mode = "SEQUENTIAL"
    else:
        execution_mode = "PARALLEL"

    disruption_savings = max(0, total_sum_durations - bundle_duration)
    efficiency_gain = (
        round((disruption_savings / total_sum_durations) * 100.0, 1) if total_sum_durations > 0 else 0.0
    )

    return (
        bundle_duration,
        execution_mode,
        disruption_savings,
        efficiency_gain,
        requires_power_off,
        requires_track_block,
        crew_by_dept,
    )


def find_candidate_bundles(
    tasks: List[TaskItem],
    config: Optional[BundlingConfig] = None,
    section_map: Optional[Dict[str, SectionInfo]] = None,
    crew_capacities: Optional[Dict[str, int]] = None,
    max_bundle_size: Optional[int] = None,
) -> List[BundleCandidate]:
    """Identify all feasible multi-task bundle candidates (size >= 2) adhering to compatibility rules.

    Algorithm:
    1. Group tasks by physical section (or corridor if adjacent allowed).
    2. Build pairwise compatibility graph where edge (u, v) exists iff check_pairwise_compatibility is True.
    3. Enumerate all valid cliques of size 2 up to max_bundle_size.
    4. For each clique, verify joint feasibility window and total departmental crew limits.
    5. Return sorted list of deterministic BundleCandidate objects.
    """
    cfg = config or BundlingConfig()
    capacities = crew_capacities or cfg.default_crew_capacities
    limit_size = max_bundle_size or cfg.max_bundle_size
    candidates: List[BundleCandidate] = []

    if len(tasks) < 2:
        return candidates

    # Group tasks by section for efficiency (since same section is default)
    # If adjacent sections allowed, group by corridor
    if cfg.allow_adjacent_sections:
        groups: Dict[str, List[TaskItem]] = {}
        for t in tasks:
            groups.setdefault(t.corridor_id, []).append(t)
    else:
        groups = {}
        for t in tasks:
            groups.setdefault(t.section_id, []).append(t)

    for _, group_tasks in groups.items():
        if len(group_tasks) < 2:
            continue

        # Sort tasks by ID for determinism
        sorted_tasks = sorted(group_tasks, key=lambda x: x.id)
        n = len(sorted_tasks)

        # Precompute pairwise compatibility
        pairwise_compat: Dict[Tuple[int, int], CompatibilityResult] = {}
        for i in range(n):
            for j in range(i + 1, n):
                res = check_pairwise_compatibility(
                    sorted_tasks[i],
                    sorted_tasks[j],
                    config=cfg,
                    section_map=section_map,
                    crew_capacities=capacities,
                )
                if res.is_compatible:
                    pairwise_compat[(i, j)] = res

        # Generate candidates of size 2 up to limit_size
        for size in range(2, limit_size + 1):
            for combo in combinations(range(n), size):
                # Verify that all pairs in combo are compatible (Clique condition)
                all_pairs_valid = True
                for p1, p2 in combinations(combo, 2):
                    if (p1, p2) not in pairwise_compat:
                        all_pairs_valid = False
                        break

                if not all_pairs_valid:
                    continue

                bundle_task_subset = [sorted_tasks[idx] for idx in combo]

                # Check joint feasible window
                earliest_start = max(t.earliest_start for t in bundle_task_subset)
                deadline = min(t.deadline for t in bundle_task_subset)
                if earliest_start >= deadline:
                    continue

                available_window = deadline - earliest_start

                # Compute aggregate metrics
                (
                    duration,
                    mode,
                    savings,
                    efficiency,
                    pwr_off,
                    trk_blk,
                    crews,
                ) = compute_bundle_metrics(bundle_task_subset, config=cfg)

                if available_window < duration:
                    continue

                # Verify combined crew limits for multi-task combo
                crew_limit_exceeded = False
                for dept, needed in crews.items():
                    if needed > capacities.get(dept, 999):
                        crew_limit_exceeded = True
                        break

                if crew_limit_exceeded:
                    continue

                # Compile compatibility reasons
                reasons: Set[str] = set()
                for p1, p2 in combinations(combo, 2):
                    res = pairwise_compat[(p1, p2)]
                    for r in res.reasons:
                        reasons.add(r)

                if savings > 0:
                    reasons.add(
                        f"Parallel coordination saves {savings} minutes of corridor disruption ({efficiency}% gain)"
                    )

                departments = sorted({t.department for t in bundle_task_subset})
                is_cross = len(departments) > 1

                bundle_task_ids = [t.id for t in bundle_task_subset]
                bundle_id = f"BND-{bundle_task_subset[0].section_id}-" + "-".join(
                    t.id.replace("TASK-", "") for t in bundle_task_subset
                )

                # Aggregate combined priority score
                combined_priority = sum(t.priority_score for t in bundle_task_subset)

                tasks_summary = [
                    {
                        "id": t.id,
                        "title": t.title,
                        "department": t.department,
                        "asset_type": t.asset_type,
                        "duration_min": t.duration_min,
                        "priority_score": t.priority_score,
                    }
                    for t in bundle_task_subset
                ]

                candidates.append(
                    BundleCandidate(
                        bundle_id=bundle_id,
                        task_ids=bundle_task_ids,
                        section_id=bundle_task_subset[0].section_id,
                        corridor_id=bundle_task_subset[0].corridor_id,
                        departments=departments,
                        is_cross_departmental=is_cross,
                        execution_mode=mode,
                        duration_min=duration,
                        disruption_savings_min=savings,
                        efficiency_gain_pct=efficiency,
                        earliest_start=earliest_start,
                        deadline=deadline,
                        feasibility_window_min=available_window,
                        requires_power_off=pwr_off,
                        requires_track_block=trk_blk,
                        crew_needed_by_dept=crews,
                        combined_priority_score=round(combined_priority, 2),
                        compatibility_reasons=sorted(reasons),
                        tasks_summary=tasks_summary,
                    )
                )

    # Sort candidates deterministically:
    # 1. Disruption savings descending (highest savings first)
    # 2. Combined priority score descending
    # 3. Bundle ID ascending
    candidates.sort(
        key=lambda c: (-c.disruption_savings_min, -c.combined_priority_score, c.bundle_id)
    )

    return candidates
