from fastapi.testclient import TestClient


def test_seed_endpoint_and_idempotency(client: TestClient) -> None:
    """Verify POST /api/seed seeds data and repeated seeding produces identical records."""
    res1 = client.post("/api/seed", json={"seed": 42, "reset": True})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "ok"
    assert data1["records"]["corridors"] == 1
    assert data1["records"]["sections"] == 8
    assert data1["records"]["tasks"] == 50
    assert data1["records"]["train_slots"] > 0
    assert data1["records"]["block_windows"] > 0

    # Reseed with same seed
    res2 = client.post("/api/seed", json={"seed": 42, "reset": True})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data1["records"] == data2["records"]


def test_corridors_and_sections_api(client: TestClient) -> None:
    """Verify corridor and section listing and detail endpoints."""
    client.post("/api/seed", json={"seed": 42, "reset": True})

    # List corridors
    res = client.get("/api/corridors")
    assert res.status_code == 200
    corridors = res.json()
    assert len(corridors) == 1
    corr_id = corridors[0]["id"]

    # Get corridor detail
    res = client.get(f"/api/corridors/{corr_id}")
    assert res.status_code == 200
    detail = res.json()
    assert len(detail["sections"]) == 8

    # List sections filtered by corridor
    res = client.get(f"/api/sections?corridor_id={corr_id}")
    assert res.status_code == 200
    sections = res.json()
    assert len(sections) == 8

    # Get single section
    sec_id = sections[0]["id"]
    res = client.get(f"/api/sections/{sec_id}")
    assert res.status_code == 200
    assert res.json()["id"] == sec_id


def test_tasks_crud_and_filters(client: TestClient) -> None:
    """Verify task CRUD operations, filters, and constraint validation."""
    client.post("/api/seed", json={"seed": 42, "reset": True})

    # 1. Filter tasks by department
    res = client.get("/api/tasks?department=TRACTION")
    assert res.status_code == 200
    trd_tasks = res.json()
    assert len(trd_tasks) == 15
    for t in trd_tasks:
        assert t["department"] == "TRACTION"

    # 2. Filter tasks by section
    res = client.get("/api/tasks?section_id=SEC-01")
    assert res.status_code == 200
    sec_tasks = res.json()
    assert len(sec_tasks) > 0
    for t in sec_tasks:
        assert t["section_id"] == "SEC-01"

    # 3. Create a valid task
    new_task_payload = {
        "id": "TASK-TEST-999",
        "department": "ENGINEERING",
        "section_id": "SEC-01",
        "title": "Emergency Rail Joint Welding",
        "asset_type": "Rails",
        "duration_min": 120,
        "earliest_start": 300,
        "deadline": 600,
        "criticality": 5,
        "defect_severity": 5,
        "last_done_date": "2026-08-01",
        "due_date": "2026-10-20",
        "traffic_impact": 0.85,
        "crew_needed": 3,
        "requires_power_off": False,
        "requires_track_block": True,
        "status": "PENDING",
    }
    create_res = client.post("/api/tasks", json=new_task_payload)
    assert create_res.status_code == 201
    created_task = create_res.json()
    assert created_task["id"] == "TASK-TEST-999"

    # 4. Reject infeasible task (deadline < earliest_start + duration)
    infeasible_payload = dict(new_task_payload)
    infeasible_payload["id"] = "TASK-TEST-INFEASIBLE"
    infeasible_payload["earliest_start"] = 500
    infeasible_payload["duration_min"] = 120
    infeasible_payload["deadline"] = 550  # 550 < 620
    inf_res = client.post("/api/tasks", json=infeasible_payload)
    assert inf_res.status_code == 422
    assert "Infeasible task constraints" in inf_res.json()["detail"]

    # 5. Reject task with invalid department
    invalid_dept_payload = dict(new_task_payload)
    invalid_dept_payload["id"] = "TASK-TEST-DEPT"
    invalid_dept_payload["department"] = "CATERING"
    inv_res = client.post("/api/tasks", json=invalid_dept_payload)
    assert inv_res.status_code == 422

    # 6. Reject task with nonexistent section
    invalid_sec_payload = dict(new_task_payload)
    invalid_sec_payload["id"] = "TASK-TEST-SEC"
    invalid_sec_payload["section_id"] = "SEC-NONEXISTENT"
    inv_sec_res = client.post("/api/tasks", json=invalid_sec_payload)
    assert inv_sec_res.status_code == 404

    # 7. Update task
    update_res = client.put(
        "/api/tasks/TASK-TEST-999",
        json={"title": "Updated Emergency Weld", "criticality": 4},
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Emergency Weld"
    assert update_res.json()["criticality"] == 4

    # 8. Delete task
    del_res = client.delete("/api/tasks/TASK-TEST-999")
    assert del_res.status_code == 204

    # Verify deleted
    get_res = client.get("/api/tasks/TASK-TEST-999")
    assert get_res.status_code == 404


def test_trains_windows_and_resources_api(client: TestClient) -> None:
    """Verify train timetables, maintenance windows, and resource endpoints."""
    client.post("/api/seed", json={"seed": 42, "reset": True})

    # Trains
    res = client.get("/api/trains?section_id=SEC-01")
    assert res.status_code == 200
    trains = res.json()
    assert len(trains) > 0

    # Windows
    res = client.get("/api/windows?section_id=SEC-01&is_night_window=true")
    assert res.status_code == 200
    night_windows = res.json()
    assert len(night_windows) > 0
    for w in night_windows:
        assert w["is_night_window"] is True
        assert w["duration_min"] >= 90

    # Resources
    res = client.get("/api/resources")
    assert res.status_code == 200
    resources = res.json()
    assert len(resources) == 3
    depts = {r["department"] for r in resources}
    assert depts == {"ENGINEERING", "TRACTION", "SNT"}
