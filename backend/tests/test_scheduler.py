"""Comprehensive unit and integration test suite for Section 4 CP-SAT scheduler.

Verifies:
1. Tiny hand-solved instance matches exact expected optimum and bundling.
2. Infeasible instance is detected gracefully with clear diagnostics (no crash).
3. Bundling reduces block count on a crafted cross-departmental example.
4. Determinism across 3 runs.
5. Full synthetic dataset (~50 tasks, 8 sections, 7-day horizon):
   - Solves within time limit.
   - Independent validator reports ZERO violations.
   - Siloed baseline vs optimized metrics demonstrate significant block reduction.
6. API endpoints:
   - POST /api/plans/generate
   - GET /api/plans/{id}
   - GET /api/plans
"""

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import create_app
from app.models.domain import BlockWindow, Task, TrainSlot
from app.optimizer.baseline import schedule_siloed_baseline
from app.optimizer.bundling import TaskItem
from app.optimizer.scheduler import SchedulerConfig, solve_maintenance_schedule
from app.optimizer.validator import validate_schedule
from app.seed import seed_database

CAPACITIES = {"ENGINEERING": 4, "TRACTION": 2, "SNT": 3}


def make_task_item(
    id: str,
    dept: str,
    sec_id: str = "SEC-01",
    duration: int = 120,
    earliest: int = 0,
    deadline: int = 1000,
    crew: int = 1,
    power_off: bool = False,
    asset: str = "General",
    priority: float = 80.0,
) -> TaskItem:
    return TaskItem(
        id=id,
        title=f"Task {id}",
        department=dept,
        section_id=sec_id,
        corridor_id="CORR-01",
        asset_type=asset,
        duration_min=duration,
        earliest_start=earliest,
        deadline=deadline,
        crew_needed=crew,
        requires_power_off=power_off,
        priority_score=priority,
    )


def test_tiny_hand_solved_instance_matches_optimum() -> None:
    """Hand-calculated instance: 2 cross-department tasks on SEC-01.

    Task 1: TRACTION, duration 120 min, window [0, 600], power_off=True
    Task 2: SNT, duration 90 min, window [0, 600]
    Single available window: [60, 360] (duration 300 min).

    Expected Optimum:
    - Exactly 1 block bundling both tasks in parallel.
    - Block duration = max(120, 90) = 120 min.
    - Disruption savings = (120 + 90) - 120 = 90 min.
    - Validator reports 0 violations.
    """
    t1 = make_task_item("T1", dept="TRACTION", duration=120, earliest=0, deadline=600, power_off=True)
    t2 = make_task_item("T2", dept="SNT", duration=90, earliest=0, deadline=600)

    windows = [{"id": "W1", "section_id": "SEC-01", "start_min": 60, "end_min": 360, "duration_min": 300}]

    cfg = SchedulerConfig(weight_num_blocks=1000.0, weight_disruption_minutes=5.0)
    result = solve_maintenance_schedule(
        tasks=[t1, t2],
        block_windows=windows,
        crew_capacities=CAPACITIES,
        config=cfg,
    )

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.total_blocks == 1
    assert result.total_disruption_minutes == 120
    assert result.cross_departmental_blocks == 1
    assert result.tasks_scheduled == 2

    block = result.blocks[0]
    assert set(block.task_ids) == {"T1", "T2"}
    assert block.duration_min == 120
    assert block.start_min >= 60
    assert block.end_min <= 360

    # Independent validation
    val = validate_schedule(
        blocks=result.blocks,
        tasks={"T1": t1, "T2": t2},
        train_slots=[],
        block_windows=windows,
        crew_capacities=CAPACITIES,
    )
    assert val.is_valid is True
    assert val.total_violations == 0


def test_infeasible_instance_detected_gracefully() -> None:
    """When a task requires 300 min but largest window is 120 min, return INFEASIBLE with diagnostics."""
    t1 = make_task_item("T1", dept="ENGINEERING", duration=300, earliest=0, deadline=600)
    windows = [{"id": "W1", "section_id": "SEC-01", "start_min": 60, "end_min": 180, "duration_min": 120}]

    result = solve_maintenance_schedule(
        tasks=[t1],
        block_windows=windows,
        crew_capacities=CAPACITIES,
    )

    assert result.status == "INFEASIBLE"
    assert result.total_blocks == 0
    assert len(result.infeasible_diagnostics) > 0
    assert any("ZERO permissible BlockWindows" in d for d in result.infeasible_diagnostics)


def test_bundling_reduces_blocks_vs_siloed_baseline() -> None:
    """Crafted 3-department scenario on SEC-01 during a single night window.

    ENG (120 min) + TRD (150 min) + SNT (90 min).
    Window is [60, 360] (300 min).
    Siloed baseline schedules 3 separate blocks (total disruption: 120 + 150 + 90 = 360 min).
    CP-SAT optimizer bundles into 1 block (total disruption: max(120, 150, 90) = 150 min).
    """
    t_eng = make_task_item("T_ENG", dept="ENGINEERING", duration=120, power_off=False)
    t_trd = make_task_item("T_TRD", dept="TRACTION", duration=150, power_off=True)
    t_snt = make_task_item("T_SNT", dept="SNT", duration=90, power_off=False)
    tasks = [t_eng, t_trd, t_snt]

    windows = [{"id": "W1", "section_id": "SEC-01", "start_min": 60, "end_min": 360, "duration_min": 300}]

    # Run Siloed Baseline
    base_res = schedule_siloed_baseline(tasks, windows, CAPACITIES)

    # Run CP-SAT Optimizer
    opt_res = solve_maintenance_schedule(tasks, windows, CAPACITIES)

    assert opt_res.status in ("OPTIMAL", "FEASIBLE")
    assert opt_res.total_blocks == 1
    assert opt_res.total_disruption_minutes == 150
    assert opt_res.total_blocks < base_res.total_blocks or opt_res.total_disruption_minutes < base_res.total_disruption_minutes


def test_scheduler_determinism() -> None:
    """Repeated runs with the same random seed produce identical solutions."""
    t1 = make_task_item("T1", dept="ENGINEERING", duration=90)
    t2 = make_task_item("T2", dept="TRACTION", duration=120, power_off=True)
    t3 = make_task_item("T3", dept="SNT", duration=60)
    tasks = [t1, t2, t3]
    windows = [
        {"id": "W1", "section_id": "SEC-01", "start_min": 60, "end_min": 300, "duration_min": 240},
        {"id": "W2", "section_id": "SEC-01", "start_min": 400, "end_min": 700, "duration_min": 300},
    ]

    r1 = solve_maintenance_schedule(tasks, windows, CAPACITIES)
    r2 = solve_maintenance_schedule(tasks, windows, CAPACITIES)
    r3 = solve_maintenance_schedule(tasks, windows, CAPACITIES)

    assert r1.total_blocks == r2.total_blocks == r3.total_blocks
    assert r1.total_disruption_minutes == r2.total_disruption_minutes == r3.total_disruption_minutes
    assert r1.objective_value == r2.objective_value == r3.objective_value
    assert [b.task_ids for b in r1.blocks] == [b.task_ids for b in r2.blocks]


def test_full_dataset_solves_with_zero_validator_violations() -> None:
    """GATE Requirement: Solve full 50-task synthetic dataset and verify 0 validator violations."""
    # Seed fresh DB
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db, seed=42, reset=True)

        db_tasks = db.query(Task).filter(Task.status == "PENDING").all()
        assert len(db_tasks) >= 40

        task_items = [
            make_task_item(
                id=t.id,
                dept=t.department,
                sec_id=t.section_id,
                duration=t.duration_min,
                earliest=t.earliest_start,
                deadline=t.deadline,
                crew=t.crew_needed,
                power_off=t.requires_power_off,
                asset=t.asset_type,
                priority=float(t.criticality * 20),
            )
            for t in db_tasks
        ]
        task_map = {t.id: t for t in task_items}

        windows = [
            {
                "id": w.id,
                "section_id": w.section_id,
                "start_min": w.start_min,
                "end_min": w.end_min,
                "duration_min": w.duration_min,
            }
            for w in db.query(BlockWindow).all()
        ]

        trains = [
            {
                "id": tr.id,
                "section_id": tr.section_id,
                "start_min": tr.start_min,
                "end_min": tr.end_min,
                "train_no": tr.train_no,
            }
            for tr in db.query(TrainSlot).all()
        ]

        # 1. Run Siloed Baseline
        baseline_res = schedule_siloed_baseline(task_items, windows, CAPACITIES)

        # 2. Run CP-SAT Optimizer
        cfg = SchedulerConfig(time_limit_seconds=15.0)
        opt_res = solve_maintenance_schedule(task_items, windows, CAPACITIES, config=cfg)

        assert opt_res.status in ("OPTIMAL", "FEASIBLE")
        assert opt_res.tasks_scheduled == len(task_items)
        assert opt_res.total_blocks > 0

        # Verify bundling advantage
        assert opt_res.total_blocks < baseline_res.total_blocks

        # 3. Independent Validation on Full Dataset
        val_res = validate_schedule(
            blocks=opt_res.blocks,
            tasks=task_map,
            train_slots=trains,
            block_windows=windows,
            crew_capacities=CAPACITIES,
            require_all_tasks_scheduled=True,
            expected_task_ids=set(task_map.keys()),
        )

        assert val_res.is_valid is True
        assert val_res.total_violations == 0, f"Validator violations: {val_res.violations}"
        assert "Zero train timetable collisions" in val_res.checks_passed
        assert "All blocks fully enclosed inside permissible BlockWindows" in val_res.checks_passed

    finally:
        db.close()


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db, seed=42, reset=True)
    finally:
        db.close()
    app = create_app()
    return TestClient(app)


def test_api_generate_plan_endpoint(api_client: TestClient) -> None:
    payload = {
        "name": "Integration Test Plan",
        "time_limit_seconds": 15.0,
        "weight_num_blocks": 1000.0,
        "weight_disruption_minutes": 5.0,
        "weight_priority_lateness": 1.0,
    }
    res = api_client.post("/api/plans/generate", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert "id" in data
    assert data["name"] == "Integration Test Plan"
    assert data["status"] in ("OPTIMAL", "FEASIBLE")

    # Metrics
    metrics = data["metrics"]
    assert metrics["tasks_scheduled"] > 0
    assert metrics["total_blocks"] > 0
    assert metrics["cross_departmental_blocks"] > 0

    # Comparison benchmarks
    comp = data["comparison"]
    assert comp is not None
    assert comp["block_reduction_count"] >= 0
    assert comp["optimized_blocks"] < comp["baseline_blocks"]

    # Validation
    val = data["validation"]
    assert val["is_valid"] is True
    assert val["total_violations"] == 0

    # Planned blocks
    blocks = data["planned_blocks"]
    assert len(blocks) == metrics["total_blocks"]
    assert len(blocks[0]["tasks"]) > 0


def test_api_get_plan_by_id(api_client: TestClient) -> None:
    # First generate a plan
    gen_res = api_client.post("/api/plans/generate", json={"name": "Lookup Test Plan"})
    assert gen_res.status_code == 201
    plan_id = gen_res.json()["id"]

    # Query by ID
    get_res = api_client.get(f"/api/plans/{plan_id}")
    assert get_res.status_code == 200
    plan = get_res.json()
    assert plan["id"] == plan_id
    assert plan["name"] == "Lookup Test Plan"
    assert len(plan["planned_blocks"]) > 0


def test_api_list_plans(api_client: TestClient) -> None:
    res = api_client.get("/api/plans")
    assert res.status_code == 200
    data = res.json()
    assert "total_plans" in data
    assert data["total_plans"] >= 1
    assert len(data["plans"]) == data["total_plans"]
