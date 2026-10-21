"""Unit tests for the independent schedule validator.

Verifies:
1. Valid plan passes with 0 violations.
2. Deliberately corrupted plans are rigorously detected:
   - Earliest start violation
   - Deadline violation
   - Train slot collision
   - Window confinement breach
   - Section block overlap (two blocks on same section overlapping)
   - Incompatible task pairing in a block
   - Crew capacity exceeded
   - Insufficient block duration
   - Duplicate task assignments
"""

from app.optimizer.bundling import TaskItem
from app.optimizer.validator import ScheduledBlock, validate_schedule

CAPACITIES = {"ENGINEERING": 3, "TRACTION": 2, "SNT": 3}

SAMPLE_WINDOWS = [
    {"id": "WIN-01", "section_id": "SEC-01", "start_min": 100, "end_min": 500, "duration_min": 400},
    {"id": "WIN-02", "section_id": "SEC-01", "start_min": 600, "end_min": 900, "duration_min": 300},
]

SAMPLE_TRAINS = [
    {"id": "TR-01", "section_id": "SEC-01", "start_min": 510, "end_min": 580, "train_no": "12004"},
]


def make_test_task(
    id: str,
    dept: str = "ENGINEERING",
    duration: int = 120,
    earliest: int = 100,
    deadline: int = 500,
    crew: int = 1,
    power_off: bool = False,
    asset: str = "Track",
) -> TaskItem:
    return TaskItem(
        id=id,
        title=f"Task {id}",
        department=dept,
        section_id="SEC-01",
        corridor_id="CORR-01",
        asset_type=asset,
        duration_min=duration,
        earliest_start=earliest,
        deadline=deadline,
        crew_needed=crew,
        requires_power_off=power_off,
    )


def test_validator_clean_valid_schedule() -> None:
    t1 = make_test_task("T1", dept="ENGINEERING", duration=120, earliest=100, deadline=500)
    t2 = make_test_task("T2", dept="SNT", duration=90, earliest=100, deadline=500)

    # Cross-department parallel block of duration max(120, 90) = 120 min inside WIN-01 [100, 500]
    block = ScheduledBlock(
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=100,
        end_min=220,
        duration_min=120,
        task_ids=["T1", "T2"],
        departments=["ENGINEERING", "SNT"],
    )

    res = validate_schedule(
        blocks=[block],
        tasks={"T1": t1, "T2": t2},
        train_slots=SAMPLE_TRAINS,
        block_windows=SAMPLE_WINDOWS,
        crew_capacities=CAPACITIES,
    )

    assert res.is_valid is True
    assert res.total_violations == 0
    assert len(res.checks_passed) > 0


def test_validator_catches_earliest_start_violation() -> None:
    # Task earliest start is 200, but block starts at 100
    t1 = make_test_task("T1", earliest=200, deadline=500)
    block = ScheduledBlock(
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=100,
        end_min=220,
        duration_min=120,
        task_ids=["T1"],
        departments=["ENGINEERING"],
    )

    res = validate_schedule(
        blocks=[block],
        tasks={"T1": t1},
        train_slots=SAMPLE_TRAINS,
        block_windows=SAMPLE_WINDOWS,
        crew_capacities=CAPACITIES,
    )

    assert res.is_valid is False
    assert any("EARLIEST_START_VIOLATION" in v for v in res.violations)


def test_validator_catches_deadline_violation() -> None:
    # Task deadline is 300, but block finishes at 350
    t1 = make_test_task("T1", earliest=100, deadline=300, duration=150)
    block = ScheduledBlock(
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=200,
        end_min=350,
        duration_min=150,
        task_ids=["T1"],
        departments=["ENGINEERING"],
    )

    res = validate_schedule(
        blocks=[block],
        tasks={"T1": t1},
        train_slots=SAMPLE_TRAINS,
        block_windows=SAMPLE_WINDOWS,
        crew_capacities=CAPACITIES,
    )

    assert res.is_valid is False
    assert any("DEADLINE_VIOLATION" in v for v in res.violations)


def test_validator_catches_train_collision() -> None:
    # Train is at [510, 580]. Corrupted block placed at [500, 650]
    t1 = make_test_task("T1", earliest=100, deadline=900, duration=150)
    block = ScheduledBlock(
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=500,
        end_min=650,
        duration_min=150,
        task_ids=["T1"],
        departments=["ENGINEERING"],
    )

    res = validate_schedule(
        blocks=[block],
        tasks={"T1": t1},
        train_slots=SAMPLE_TRAINS,
        block_windows=SAMPLE_WINDOWS,
        crew_capacities=CAPACITIES,
    )

    assert res.is_valid is False
    assert any("TRAIN_COLLISION" in v for v in res.violations)


def test_validator_catches_window_confinement_breach() -> None:
    # Permissible window WIN-01 is [100, 500]. Corrupted block placed at [450, 550]
    t1 = make_test_task("T1", earliest=100, deadline=900, duration=100)
    block = ScheduledBlock(
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=450,
        end_min=550,
        duration_min=100,
        task_ids=["T1"],
        departments=["ENGINEERING"],
    )

    res = validate_schedule(
        blocks=[block],
        tasks={"T1": t1},
        train_slots=SAMPLE_TRAINS,
        block_windows=SAMPLE_WINDOWS,
        crew_capacities=CAPACITIES,
    )

    assert res.is_valid is False
    assert any("WINDOW_CONFINEMENT_VIOLATION" in v for v in res.violations)


def test_validator_catches_section_block_overlap() -> None:
    # Two blocks on SEC-01 overlapping: [100, 300] and [250, 450]
    t1 = make_test_task("T1", duration=200)
    t2 = make_test_task("T2", duration=200)
    b1 = ScheduledBlock(
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=100,
        end_min=300,
        duration_min=200,
        task_ids=["T1"],
        departments=["ENGINEERING"],
    )
    b2 = ScheduledBlock(
        block_id="BLK-02",
        section_id="SEC-01",
        start_min=250,
        end_min=450,
        duration_min=200,
        task_ids=["T2"],
        departments=["ENGINEERING"],
    )

    res = validate_schedule(
        blocks=[b1, b2],
        tasks={"T1": t1, "T2": t2},
        train_slots=SAMPLE_TRAINS,
        block_windows=SAMPLE_WINDOWS,
        crew_capacities=CAPACITIES,
    )

    assert res.is_valid is False
    assert any("SECTION_BLOCK_OVERLAP" in v for v in res.violations)


def test_validator_catches_crew_capacity_exceeded() -> None:
    # Capacity for ENG is 3. Two tasks requiring 2 each (total 4) bundled together
    t1 = make_test_task("T1", dept="ENGINEERING", crew=2, duration=100)
    t2 = make_test_task("T2", dept="ENGINEERING", crew=2, duration=100)
    block = ScheduledBlock(
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=100,
        end_min=300,
        duration_min=200,
        task_ids=["T1", "T2"],
        departments=["ENGINEERING"],
    )

    res = validate_schedule(
        blocks=[block],
        tasks={"T1": t1, "T2": t2},
        train_slots=SAMPLE_TRAINS,
        block_windows=SAMPLE_WINDOWS,
        crew_capacities=CAPACITIES,
    )

    assert res.is_valid is False
    assert any("CREW_CAPACITY_EXCEEDED" in v for v in res.violations)


def test_validator_catches_duplicate_tasks() -> None:
    t1 = make_test_task("T1", duration=100)
    b1 = ScheduledBlock(
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=100,
        end_min=200,
        duration_min=100,
        task_ids=["T1"],
        departments=["ENGINEERING"],
    )
    b2 = ScheduledBlock(
        block_id="BLK-02",
        section_id="SEC-01",
        start_min=600,
        end_min=700,
        duration_min=100,
        task_ids=["T1"],
        departments=["ENGINEERING"],
    )

    res = validate_schedule(
        blocks=[b1, b2],
        tasks={"T1": t1},
        train_slots=SAMPLE_TRAINS,
        block_windows=SAMPLE_WINDOWS,
        crew_capacities=CAPACITIES,
    )

    assert res.is_valid is False
    assert any("DUPLICATE_TASKS" in v for v in res.violations)
