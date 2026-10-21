"""Independent Plan Validator for UnityTrack.

This module is completely decoupled from the CP-SAT solver and the database.
It independently inspects any schedule/plan against the fundamental railway constraints:
1. Task time windows: Task start >= earliest_start and task finish <= deadline.
2. Train slot collision: NO block overlaps with any train slot on the same section.
3. Block window confinement: Every block is strictly within an allowed maintenance window.
4. Section exclusivity: No two maintenance blocks on the same section overlap in time.
5. Department resource capacity: Crew requirements per department in any window <= capacity limit.
6. Mutual task compatibility: All tasks sharing a block must be pairwise compatible (Section 3).
7. Block duration sufficiency: Block duration covers the required execution duration of its tasks.
8. Task completeness: Every expected task is scheduled exactly once without duplicates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.optimizer.bundling import (
    BundlingConfig,
    SectionInfo,
    TaskItem,
    check_pairwise_compatibility,
    compute_bundle_metrics,
)


@dataclass
class ScheduledTaskAssignment:
    """Assignment details for a single task within a scheduled plan."""

    task_id: str
    block_id: str
    section_id: str
    start_min: int
    duration_min: int
    finish_min: int
    department: str
    is_delayed: bool = False
    delay_minutes: int = 0


@dataclass
class ScheduledBlock:
    """A scheduled maintenance block in a plan."""

    block_id: str
    section_id: str
    start_min: int
    end_min: int
    duration_min: int
    task_ids: List[str]
    departments: List[str]
    requires_power_off: bool = False
    requires_track_block: bool = True


@dataclass
class ValidationResult:
    """Outcome of the independent schedule validation."""

    is_valid: bool
    total_violations: int
    violations: List[str] = field(default_factory=list)
    checks_passed: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


def validate_schedule(
    blocks: List[ScheduledBlock],
    tasks: Dict[str, TaskItem],
    train_slots: List[Dict[str, Any]],
    block_windows: List[Dict[str, Any]],
    crew_capacities: Dict[str, int],
    section_map: Optional[Dict[str, SectionInfo]] = None,
    allow_adjacent_sections: bool = False,
    require_all_tasks_scheduled: bool = False,
    expected_task_ids: Optional[Set[str]] = None,
) -> ValidationResult:
    """Re-verify all hard constraints on a proposed schedule without using the solver."""
    violations: List[str] = []
    checks_passed: List[str] = []

    # 1. Task Uniqueness & Completeness Check
    scheduled_task_counts: Dict[str, int] = {}
    for b in blocks:
        for tid in b.task_ids:
            scheduled_task_counts[tid] = scheduled_task_counts.get(tid, 0) + 1

    duplicate_tasks = [tid for tid, cnt in scheduled_task_counts.items() if cnt > 1]
    if duplicate_tasks:
        violations.append(
            f"DUPLICATE_TASKS: Tasks scheduled in multiple blocks: {duplicate_tasks}"
        )
    else:
        checks_passed.append("No duplicate task assignments")

    if require_all_tasks_scheduled and expected_task_ids:
        missing = expected_task_ids - set(scheduled_task_counts.keys())
        if missing:
            violations.append(
                f"MISSING_TASKS: {len(missing)} tasks were not scheduled: {sorted(list(missing))[:5]}..."
            )
        else:
            checks_passed.append(f"All {len(expected_task_ids)} expected tasks are scheduled")

    # 2. Check Each Block's Confinement in Permissible Windows & Train Collision
    # Index train slots and block windows by section
    trains_by_sec: Dict[str, List[Tuple[int, int, str]]] = {}
    for slot in train_slots:
        trains_by_sec.setdefault(slot["section_id"], []).append(
            (slot["start_min"], slot["end_min"], slot.get("train_no", "Unknown"))
        )

    windows_by_sec: Dict[str, List[Tuple[int, int]]] = {}
    for w in block_windows:
        windows_by_sec.setdefault(w["section_id"], []).append((w["start_min"], w["end_min"]))

    blocks_by_sec: Dict[str, List[ScheduledBlock]] = {}

    for b in blocks:
        blocks_by_sec.setdefault(b.section_id, []).append(b)

        # Check: Start < End
        if b.start_min >= b.end_min:
            violations.append(
                f"INVALID_INTERVAL: Block '{b.block_id}' has invalid interval [{b.start_min}, {b.end_min}]"
            )

        if b.duration_min != (b.end_min - b.start_min):
            violations.append(
                f"DURATION_MISMATCH: Block '{b.block_id}' duration_min {b.duration_min} "
                f"does not match end_min - start_min ({b.end_min - b.start_min})"
            )

        # Check: Confinement within at least one valid BlockWindow
        sec_windows = windows_by_sec.get(b.section_id, [])
        is_inside_window = any(
            (w_start <= b.start_min and b.end_min <= w_end) for w_start, w_end in sec_windows
        )
        if not is_inside_window:
            violations.append(
                f"WINDOW_CONFINEMENT_VIOLATION: Block '{b.block_id}' [{b.start_min}, {b.end_min}] "
                f"on section '{b.section_id}' is not completely enclosed in any permissible BlockWindow"
            )

        # Check: Direct Train Collision
        sec_trains = trains_by_sec.get(b.section_id, [])
        for t_start, t_end, t_no in sec_trains:
            # Overlap exists if start < t_end and end > t_start
            if max(b.start_min, t_start) < min(b.end_min, t_end):
                violations.append(
                    f"TRAIN_COLLISION: Block '{b.block_id}' [{b.start_min}, {b.end_min}] "
                    f"collides with Train '{t_no}' [{t_start}, {t_end}] on section '{b.section_id}'"
                )

        # 3. Check Tasks inside the Block
        block_task_items: List[TaskItem] = []
        for tid in b.task_ids:
            if tid not in tasks:
                violations.append(
                    f"UNKNOWN_TASK: Block '{b.block_id}' references unknown task '{tid}'"
                )
                continue

            t = tasks[tid]
            block_task_items.append(t)

            # Check section match (or adjacent if enabled)
            if t.section_id != b.section_id:
                if not allow_adjacent_sections:
                    violations.append(
                        f"TASK_SECTION_MISMATCH: Task '{t.id}' (section '{t.section_id}') "
                        f"cannot be scheduled in block '{b.block_id}' on section '{b.section_id}'"
                    )
                elif section_map:
                    sec_t = section_map.get(t.section_id)
                    sec_b = section_map.get(b.section_id)
                    if (
                        not sec_t
                        or not sec_b
                        or abs(sec_t.order_index - sec_b.order_index) > 1
                    ):
                        violations.append(
                            f"TASK_SECTION_NON_ADJACENT: Task '{t.id}' section '{t.section_id}' "
                            f"is not adjacent to block section '{b.section_id}'"
                        )

            # Check time window: earliest start & deadline
            if b.start_min < t.earliest_start:
                violations.append(
                    f"EARLIEST_START_VIOLATION: Task '{t.id}' earliest start is {t.earliest_start}, "
                    f"but block starts at {b.start_min}"
                )

            if b.end_min > t.deadline:
                violations.append(
                    f"DEADLINE_VIOLATION: Task '{t.id}' deadline is {t.deadline}, "
                    f"but block finishes at {b.end_min}"
                )

        # 4. Check Mutual Compatibility of Tasks in Block (Section 3 rules)
        cfg = BundlingConfig(allow_adjacent_sections=allow_adjacent_sections)
        for i in range(len(block_task_items)):
            for j in range(i + 1, len(block_task_items)):
                res = check_pairwise_compatibility(
                    block_task_items[i],
                    block_task_items[j],
                    config=cfg,
                    section_map=section_map,
                    crew_capacities=crew_capacities,
                )
                if not res.is_compatible:
                    violations.append(
                        f"MUTUAL_COMPATIBILITY_VIOLATION: In block '{b.block_id}', tasks "
                        f"'{block_task_items[i].id}' and '{block_task_items[j].id}' are incompatible: "
                        f"{res.conflict_reason}"
                    )

        # 5. Check Block Duration Sufficiency
        if block_task_items:
            (
                req_dur,
                _,
                _,
                _,
                _,
                _,
                crews,
            ) = compute_bundle_metrics(block_task_items, config=cfg)
            if b.duration_min < req_dur:
                violations.append(
                    f"INSUFFICIENT_BLOCK_DURATION: Block '{b.block_id}' duration is {b.duration_min} min, "
                    f"but bundled tasks require {req_dur} min"
                )

            # 6. Check Department Resource Capacity in Block
            for dept, needed in crews.items():
                cap = crew_capacities.get(dept, 999)
                if needed > cap:
                    violations.append(
                        f"CREW_CAPACITY_EXCEEDED: Block '{b.block_id}' requires {needed} crew for {dept}, "
                        f"exceeding window capacity of {cap}"
                    )

    # 7. Check Section Exclusivity (No two blocks on the same section overlap)
    for sec_id, sec_blocks in blocks_by_sec.items():
        sorted_sec_blocks = sorted(sec_blocks, key=lambda x: x.start_min)
        for i in range(len(sorted_sec_blocks) - 1):
            curr_b = sorted_sec_blocks[i]
            next_b = sorted_sec_blocks[i + 1]
            if curr_b.end_min > next_b.start_min:
                violations.append(
                    f"SECTION_BLOCK_OVERLAP: Blocks '{curr_b.block_id}' [{curr_b.start_min}, {curr_b.end_min}] "
                    f"and '{next_b.block_id}' [{next_b.start_min}, {next_b.end_min}] overlap on section '{sec_id}'"
                )

    if not any("TRAIN_COLLISION" in v for v in violations):
        checks_passed.append("Zero train timetable collisions")

    if not any("WINDOW_CONFINEMENT" in v for v in violations):
        checks_passed.append("All blocks fully enclosed inside permissible BlockWindows")

    if not any("SECTION_BLOCK_OVERLAP" in v for v in violations):
        checks_passed.append("Strict section exclusivity (no overlapping blocks)")

    if not any("CREW_CAPACITY" in v for v in violations):
        checks_passed.append("All departmental crew allocations within capacity")

    if not any("MUTUAL_COMPATIBILITY" in v for v in violations):
        checks_passed.append("All bundled tasks satisfy pairwise compatibility")

    if not any("VIOLATION" in v for v in violations):
        checks_passed.append("All task time windows (earliest start & deadline) respected")

    is_valid = len(violations) == 0

    return ValidationResult(
        is_valid=is_valid,
        total_violations=len(violations),
        violations=violations,
        checks_passed=checks_passed,
        stats={
            "total_blocks": len(blocks),
            "total_tasks_scheduled": len(scheduled_task_counts),
            "total_disruption_minutes": sum(b.duration_min for b in blocks),
        },
    )
