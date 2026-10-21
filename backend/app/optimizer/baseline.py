"""Siloed baseline scheduler simulating isolated departmental maintenance planning.

In the current Indian Railways operational baseline:
- Engineering (ENG), Traction (TRD), and Signal & Telecom (SNT) plan independently.
- There is ZERO cross-departmental coordination or bundling.
- Each department schedules its own tasks using greedy earliest-feasible assignment.
- This creates excessive separate line blocks and higher total corridor disruption.

Used for comparison benchmarking against UnityTrack's CP-SAT cross-departmental optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.optimizer.bundling import TaskItem
from app.optimizer.validator import ScheduledBlock, ScheduledTaskAssignment


@dataclass
class BaselinePlanResult:
    """Outcome of the siloed departmental baseline scheduling."""

    blocks: List[ScheduledBlock]
    task_assignments: List[ScheduledTaskAssignment]
    total_blocks: int
    total_disruption_minutes: int
    scheduled_tasks_count: int
    delayed_tasks_count: int
    total_delay_minutes: int
    department_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def schedule_siloed_baseline(
    tasks: List[TaskItem],
    block_windows: List[Dict[str, Any]],
    crew_capacities: Dict[str, int],
) -> BaselinePlanResult:
    """Run greedy earliest-feasible scheduling per department in complete isolation."""
    # Group tasks by department
    dept_tasks: Dict[str, List[TaskItem]] = {}
    for t in tasks:
        dept_tasks.setdefault(t.department, []).append(t)

    all_blocks: List[ScheduledBlock] = []
    all_assignments: List[ScheduledTaskAssignment] = []
    block_counter = 1

    # Track occupied intervals on each section: list of (start_min, end_min, block_id)
    occupied_by_section: Dict[str, List[tuple[int, int]]] = {}

    # Track crew used per department in each window: (window_id, department) -> crew_used
    window_crew_used: Dict[tuple[str, str], int] = {}

    # Sort windows by start_min ascending for greedy earliest search
    sorted_windows = sorted(block_windows, key=lambda w: (w["start_min"], w["end_min"]))

    # Index windows by section
    windows_by_sec: Dict[str, List[Dict[str, Any]]] = {}
    for w in sorted_windows:
        windows_by_sec.setdefault(w["section_id"], []).append(w)

    delayed_tasks_count = 0
    total_delay_minutes = 0
    dept_stats: Dict[str, Dict[str, Any]] = {}

    # Process each department independently
    for dept, d_tasks in dept_tasks.items():
        # Sort department tasks: higher priority score first, then earlier deadline
        sorted_dept_tasks = sorted(
            d_tasks, key=lambda t: (-t.priority_score, t.deadline, t.earliest_start)
        )
        cap = crew_capacities.get(dept, 999)

        dept_scheduled = 0
        dept_delayed = 0
        dept_disruption = 0

        for t in sorted_dept_tasks:
            sec_windows = windows_by_sec.get(t.section_id, [])
            scheduled = False

            # Search for earliest feasible window meeting task requirements
            for w in sec_windows:
                w_start = w["start_min"]
                w_end = w["end_min"]
                w_id = w.get("id", f"{w['section_id']}_{w_start}")

                # Check if window can fit task duration
                if (w_end - w_start) < t.duration_min:
                    continue

                # Check window crew capacity for this department
                current_crew = window_crew_used.get((w_id, dept), 0)
                if current_crew + t.crew_needed > cap:
                    continue

                # In baseline siloed mode: search for free sub-interval within window w
                sec_occupied = sorted(
                    occupied_by_section.get(t.section_id, []), key=lambda x: x[0]
                )

                cursor = max(w_start, t.earliest_start)
                found_slot = False

                while cursor + t.duration_min <= w_end:
                    collides = False
                    for occ_start, occ_end in sec_occupied:
                        if max(cursor, occ_start) < min(cursor + t.duration_min, occ_end):
                            collides = True
                            cursor = max(cursor + 1, occ_end)
                            break
                    if not collides:
                        earliest_possible = cursor
                        candidate_finish = cursor + t.duration_min
                        found_slot = True
                        break

                if not found_slot:
                    continue

                # Found feasible slot!
                is_delayed = candidate_finish > t.deadline
                delay_min = max(0, candidate_finish - t.deadline)

                block_id = f"BASE-BLK-{block_counter:03d}"
                block_counter += 1

                new_block = ScheduledBlock(
                    block_id=block_id,
                    section_id=t.section_id,
                    start_min=earliest_possible,
                    end_min=candidate_finish,
                    duration_min=t.duration_min,
                    task_ids=[t.id],
                    departments=[dept],
                    requires_power_off=t.requires_power_off,
                    requires_track_block=t.requires_track_block,
                )

                assignment = ScheduledTaskAssignment(
                    task_id=t.id,
                    block_id=block_id,
                    section_id=t.section_id,
                    start_min=earliest_possible,
                    duration_min=t.duration_min,
                    finish_min=candidate_finish,
                    department=dept,
                    is_delayed=is_delayed,
                    delay_minutes=delay_min,
                )

                all_blocks.append(new_block)
                all_assignments.append(assignment)
                occupied_by_section.setdefault(t.section_id, []).append(
                    (earliest_possible, candidate_finish)
                )
                window_crew_used[(w_id, dept)] = current_crew + t.crew_needed

                dept_scheduled += 1
                dept_disruption += t.duration_min
                if is_delayed:
                    dept_delayed += 1
                    delayed_tasks_count += 1
                    total_delay_minutes += delay_min

                scheduled = True
                break

            if not scheduled:
                # If cannot be scheduled inside any regular window, record as unassigned/delayed
                delayed_tasks_count += 1

        dept_stats[dept] = {
            "total_tasks": len(d_tasks),
            "scheduled": dept_scheduled,
            "delayed": dept_delayed,
            "disruption_minutes": dept_disruption,
        }

    # Sort blocks by start time
    all_blocks.sort(key=lambda b: (b.start_min, b.section_id))

    return BaselinePlanResult(
        blocks=all_blocks,
        task_assignments=all_assignments,
        total_blocks=len(all_blocks),
        total_disruption_minutes=sum(b.duration_min for b in all_blocks),
        scheduled_tasks_count=len(all_assignments),
        delayed_tasks_count=delayed_tasks_count,
        total_delay_minutes=total_delay_minutes,
        department_metrics=dept_stats,
    )
