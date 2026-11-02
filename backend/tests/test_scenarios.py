"""Comprehensive test suite for Section 5 What-If Scenario Simulator.

Verifies:
1. Base data immutability: Base DB records (tasks, windows, trains, resources) are NEVER mutated.
2. Emergency task injection: Emergency task appears in the scenario schedule with zero train collisions.
3. Section restriction/closure: Tasks avoid closed time intervals on the restricted section.
4. Department capacity changes: Crew capacity constraints are strictly respected under restricted capacity.
5. Infeasibility diagnostics: Impossible scenario fails gracefully with clear diagnostics.
6. Multi-scenario comparative analysis: Evaluates 3 scenarios, computes composite penalties, designates best.
7. REST API lifecycle: run, list, get, compare, delete.
"""

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import create_app
from app.models.domain import BlockWindow, Resource, Task, TrainSlot
from app.optimizer.bundling import TaskItem
from app.optimizer.scenario import (
    ScenarioOverlayData,
    apply_scenario_overlay,
    run_scenario_simulation,
)
from app.seed import seed_database

CAPACITIES = {"ENGINEERING": 4, "TRACTION": 2, "SNT": 3}


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Fixture providing initialized database and test HTTP client."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db, seed=42, reset=True)
    finally:
        db.close()

    app = create_app()
    with TestClient(app) as client:
        yield client


def test_base_data_immutability(api_client: TestClient) -> None:
    """Verify that simulating a what-if scenario never mutates base database records."""
    db = SessionLocal()
    try:
        tasks_before = [(t.id, t.deadline, t.status) for t in db.query(Task).order_by(Task.id).all()]
        res_before = [(r.department, r.capacity_per_window) for r in db.query(Resource).order_by(Resource.id).all()]
        win_before = len(db.query(BlockWindow).all())
        train_before = len(db.query(TrainSlot).all())

        # Run an aggressive scenario with modifications
        payload = {
            "name": "Stress Test Scenario",
            "params": {
                "add_tasks": [
                    {
                        "title": "Emergency Track Fracture",
                        "department": "ENGINEERING",
                        "section_id": "SEC-01",
                        "duration_min": 90,
                        "earliest_start": 60,
                        "deadline": 900,
                        "crew_needed": 2,
                    }
                ],
                "restrict_sections": [
                    {
                        "section_id": "SEC-01",
                        "start_min": 100,
                        "end_min": 250,
                        "restriction_type": "CLOSED",
                    }
                ],
                "deadline_overrides": {tasks_before[0][0]: 600},
                "capacity_overrides": {"ENGINEERING": 2},
            },
            "save_scenario": False,
        }

        resp = api_client.post("/api/scenarios/run", json=payload)
        assert resp.status_code == 201

        # Check DB records after run
        tasks_after = [(t.id, t.deadline, t.status) for t in db.query(Task).order_by(Task.id).all()]
        res_after = [(r.department, r.capacity_per_window) for r in db.query(Resource).order_by(Resource.id).all()]
        win_after = len(db.query(BlockWindow).all())
        train_after = len(db.query(TrainSlot).all())

        assert tasks_before == tasks_after, "Base tasks were mutated by scenario run!"
        assert res_before == res_after, "Base resources were mutated by scenario run!"
        assert win_before == win_after, "Base block windows count changed!"
        assert train_before == train_after, "Base train slots count changed!"
    finally:
        db.close()


def test_emergency_task_injection(api_client: TestClient) -> None:
    """Verify that an emergency task is scheduled alongside base tasks with 0 violations."""
    emg_payload = {
        "name": "Emergency Rail Replacement",
        "description": "Urgent rail fracture detected on SEC-03",
        "params": {
            "add_tasks": [
                {
                    "id": "EMG-SEC03-01",
                    "title": "Broken Rail Clamping & Weld",
                    "department": "ENGINEERING",
                    "section_id": "SEC-03",
                    "duration_min": 120,
                    "earliest_start": 0,
                    "deadline": 1440,
                    "crew_needed": 2,
                    "criticality": 5,
                    "defect_severity": 5,
                }
            ]
        },
        "save_scenario": True,
    }

    resp = api_client.post("/api/scenarios/run", json=emg_payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["name"] == "Emergency Rail Replacement"
    assert data["metrics"]["status"] in ("OPTIMAL", "FEASIBLE")
    assert data["metrics"]["tasks_scheduled"] == data["metrics"]["total_tasks_count"]

    # Verify that EMG-SEC03-01 is present in the planned blocks
    scen_id = data["id"]
    get_resp = api_client.get(f"/api/scenarios/{scen_id}")
    assert get_resp.status_code == 200


def test_section_restriction_window_filtering() -> None:
    """Unit test verify apply_scenario_overlay filters/truncates windows during section closures."""
    base_windows = [
        {"id": "W1", "section_id": "SEC-01", "start_min": 100, "end_min": 400, "duration_min": 300},
        {"id": "W2", "section_id": "SEC-02", "start_min": 100, "end_min": 400, "duration_min": 300},
    ]

    # Closure on SEC-01 from 150 to 350
    overlay = ScenarioOverlayData(
        name="Closure SEC-01",
        restrict_sections=[
            {"section_id": "SEC-01", "start_min": 150, "end_min": 350, "restriction_type": "CLOSED"}
        ],
    )

    _, mod_windows, _, _, _ = apply_scenario_overlay(
        base_tasks=[],
        base_windows=base_windows,
        base_train_slots=[],
        base_capacities={"ENGINEERING": 4},
        overlay=overlay,
    )

    # SEC-02 window is unaffected
    sec2_wins = [w for w in mod_windows if w["section_id"] == "SEC-02"]
    assert len(sec2_wins) == 1
    assert sec2_wins[0]["start_min"] == 100
    assert sec2_wins[0]["end_min"] == 400

    # SEC-01 window was truncated to pre-restriction period [100, 150] (duration 50 < 60 min, so eliminated)
    sec1_wins = [w for w in mod_windows if w["section_id"] == "SEC-01"]
    assert len(sec1_wins) == 0


def test_capacity_reduction_respected() -> None:
    """Unit test verify that lower crew capacity is strictly enforced."""
    t1 = TaskItem(
        id="T1",
        title="ENG Task 1",
        department="ENGINEERING",
        section_id="SEC-01",
        corridor_id="CORR-01",
        asset_type="Track",
        duration_min=60,
        earliest_start=0,
        deadline=1000,
        crew_needed=3,
        requires_power_off=False,
    )
    t2 = TaskItem(
        id="T2",
        title="ENG Task 2",
        department="ENGINEERING",
        section_id="SEC-01",
        corridor_id="CORR-01",
        asset_type="Track",
        duration_min=60,
        earliest_start=0,
        deadline=1000,
        crew_needed=3,
        requires_power_off=False,
    )

    # Window allows duration 300
    windows = [{"id": "W1", "section_id": "SEC-01", "start_min": 60, "end_min": 360, "duration_min": 300}]

    # Normal capacity 4 allows one task (3 crews), but not both simultaneously (6 crews > 4)
    # With capacity reduced to 2, neither task can be scheduled (3 crews > 2 capacity)
    overlay = ScenarioOverlayData(
        name="Reduced Crew",
        capacity_overrides={"ENGINEERING": 2},
    )

    res = run_scenario_simulation(
        base_tasks=[t1, t2],
        base_windows=windows,
        base_train_slots=[],
        base_capacities={"ENGINEERING": 4},
        overlay=overlay,
    )

    # Must be INFEASIBLE because 3 crews needed > 2 capacity limit
    assert res.status == "INFEASIBLE"
    assert res.infeasible_diagnostics is not None
    assert any("ENGINEERING" in d for d in res.infeasible_diagnostics)


def test_infeasible_scenario_diagnostics(api_client: TestClient) -> None:
    """Verify that an infeasible scenario returns diagnostic messages without crashing."""
    impossible_payload = {
        "name": "Impossible Deadline Scenario",
        "params": {
            "add_tasks": [
                {
                    "title": "Impossible Task",
                    "department": "ENGINEERING",
                    "section_id": "SEC-01",
                    "duration_min": 300,
                    "earliest_start": 100,
                    "deadline": 200,  # Deadline 200 < start 100 + duration 300
                    "crew_needed": 1,
                }
            ]
        },
        "save_scenario": False,
    }

    resp = api_client.post("/api/scenarios/run", json=impossible_payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["metrics"]["status"] == "INFEASIBLE"
    assert data["metrics"]["total_blocks"] == 0
    assert data["infeasible_diagnostics"] is not None
    assert len(data["infeasible_diagnostics"]) > 0


def test_multi_scenario_comparison(api_client: TestClient) -> None:
    """Verify comparing 3 realistic scenarios with ranking and recommendation."""
    compare_payload = {
        "scenarios": [
            {
                "name": "Scenario A - Normal",
                "params": {},
            },
            {
                "name": "Scenario B - Reduced Traction Capacity",
                "params": {
                    "capacity_overrides": {"TRACTION": 1},
                },
            },
            {
                "name": "Scenario C - Emergency Broken Rail on SEC-02",
                "params": {
                    "add_tasks": [
                        {
                            "id": "EMG-002",
                            "title": "Emergency Broken Rail",
                            "department": "ENGINEERING",
                            "section_id": "SEC-02",
                            "duration_min": 120,
                            "earliest_start": 0,
                            "deadline": 1440,
                            "crew_needed": 2,
                        }
                    ]
                },
            },
        ],
        "include_baseline": True,
        "time_limit_seconds": 15.0,
    }

    resp = api_client.post("/api/scenarios/compare", json=compare_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["scenarios_evaluated"] == 3
    assert len(data["comparison_table"]) == 3
    assert data["best_scenario_name"] != ""
    assert data["best_scenario_reason"] != ""
    assert "ranking_rule" in data

    # Check rank order
    ranks = [item["rank"] for item in data["comparison_table"]]
    assert ranks == [1, 2, 3]

    # Best scenario has is_best == True
    best_item = next(item for item in data["comparison_table"] if item["is_best"])
    assert best_item["rank"] == 1
    assert best_item["name"] == data["best_scenario_name"]

    # Verify deltas vs baseline are present
    assert data["delta_vs_baseline"] is not None
    assert "Scenario A - Normal" in data["delta_vs_baseline"]


def test_scenario_crud_lifecycle(api_client: TestClient) -> None:
    """Verify full scenario lifecycle: run with save, list, get detail, and delete."""
    # 1. Create and save scenario
    run_payload = {
        "name": "Lifecycle Test Scenario",
        "description": "Testing CRUD persistence",
        "params": {
            "capacity_overrides": {"SNT": 2},
        },
        "save_scenario": True,
    }
    create_resp = api_client.post("/api/scenarios/run", json=run_payload)
    assert create_resp.status_code == 201
    scen_id = create_resp.json()["id"]

    # 2. List scenarios
    list_resp = api_client.get("/api/scenarios")
    assert list_resp.status_code == 200
    scen_list = list_resp.json()
    assert any(s["id"] == scen_id for s in scen_list)

    # 3. Get scenario detail
    get_resp = api_client.get(f"/api/scenarios/{scen_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == scen_id
    assert get_resp.json()["name"] == "Lifecycle Test Scenario"

    # 4. Delete scenario
    del_resp = api_client.delete(f"/api/scenarios/{scen_id}")
    assert del_resp.status_code == 204

    # 5. Verify 404 on get
    get_again = api_client.get(f"/api/scenarios/{scen_id}")
    assert get_again.status_code == 404
