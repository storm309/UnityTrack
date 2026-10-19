"""Comprehensive tests for Priority Scoring Engine.

Includes 8+ hand-calculated test cases with exact arithmetic documented in comments,
edge cases, weights validation, contributions summation, ordering stability, and API tests.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.optimizer.priority import (
    BAND_CRITICAL,
    BAND_HIGH,
    BAND_LOW,
    BAND_MEDIUM,
    PriorityWeights,
    calculate_task_priority,
    rank_tasks_by_priority,
)

TODAY = date(2026, 10, 19)


# ==============================================================================
# HAND-CALCULATED ARITHMETIC TESTS (8 DISTINCT CASES)
# ==============================================================================


def test_hand_calc_case_1_all_minimum() -> None:
    """Case 1: All minimum values (zero/minimum edge case).

    Arithmetic:
    - criticality = 1 -> norm = (1-1)/4 = 0.0
    - defect_severity = 1 -> norm = (1-1)/4 = 0.0
    - due_date = 2026-10-25 (> today 2026-10-19) -> overdue_ratio = 0.0
    - traffic_impact = 0.0
    - c_crit = 100 * 0.35 * 0.0 = 0.0
    - c_sev = 100 * 0.30 * 0.0 = 0.0
    - c_overdue = 100 * 0.20 * 0.0 = 0.0
    - c_traffic = 100 * 0.15 * 0.0 = 0.0
    - Expected score = 0.00, Band = LOW
    """
    task = {
        "id": "T1",
        "criticality": 1,
        "defect_severity": 1,
        "due_date": "2026-10-25",
        "traffic_impact": 0.0,
    }
    res = calculate_task_priority(task, today=TODAY)
    assert res.score == 0.00
    assert res.contributions.criticality == 0.00
    assert res.contributions.defect_severity == 0.00
    assert res.contributions.overdue_ratio == 0.00
    assert res.contributions.traffic_impact == 0.00
    assert res.priority_band == BAND_LOW


def test_hand_calc_case_2_all_maximum() -> None:
    """Case 2: All maximum values (100.0 max edge case).

    Arithmetic:
    - criticality = 5 -> norm = (5-1)/4 = 1.0
    - defect_severity = 5 -> norm = (5-1)/4 = 1.0
    - due_date = 2026-09-01, last_done = 2026-08-01 (interval = 31 days)
      today - due_date = 48 days -> 48 / 31 = 1.548 -> clamped to 1.0
    - traffic_impact = 1.0
    - c_crit = 100 * 0.35 * 1.0 = 35.00
    - c_sev = 100 * 0.30 * 1.0 = 30.00
    - c_overdue = 100 * 0.20 * 1.0 = 20.00
    - c_traffic = 100 * 0.15 * 1.0 = 15.00
    - Expected score = 35 + 30 + 20 + 15 = 100.00, Band = CRITICAL
    """
    task = {
        "id": "T2",
        "criticality": 5,
        "defect_severity": 5,
        "due_date": "2026-09-01",
        "last_done_date": "2026-08-01",
        "traffic_impact": 1.0,
    }
    res = calculate_task_priority(task, today=TODAY)
    assert res.score == 100.00
    assert res.contributions.criticality == 35.00
    assert res.contributions.defect_severity == 30.00
    assert res.contributions.overdue_ratio == 20.00
    assert res.contributions.traffic_impact == 15.00
    assert res.priority_band == BAND_CRITICAL


def test_hand_calc_case_3_not_overdue_medium() -> None:
    """Case 3: Not overdue (future due date) with moderate values.

    Arithmetic:
    - criticality = 3 -> norm = (3-1)/4 = 0.50
    - defect_severity = 3 -> norm = (3-1)/4 = 0.50
    - due_date = 2026-10-29 (future) -> overdue_ratio = 0.0
    - traffic_impact = 0.50
    - c_crit = 100 * 0.35 * 0.50 = 17.50
    - c_sev = 100 * 0.30 * 0.50 = 15.00
    - c_overdue = 100 * 0.20 * 0.0 = 0.00
    - c_traffic = 100 * 0.15 * 0.50 = 7.50
    - Expected score = 17.50 + 15.00 + 0.00 + 7.50 = 40.00, Band = MEDIUM
    """
    task = {
        "id": "T3",
        "criticality": 3,
        "defect_severity": 3,
        "due_date": "2026-10-29",
        "traffic_impact": 0.50,
    }
    res = calculate_task_priority(task, today=TODAY)
    assert res.score == 40.00
    assert res.contributions.criticality == 17.50
    assert res.contributions.defect_severity == 15.00
    assert res.contributions.overdue_ratio == 0.00
    assert res.contributions.traffic_impact == 7.50
    assert res.priority_band == BAND_MEDIUM


def test_hand_calc_case_4_heavily_overdue_clamp() -> None:
    """Case 4: Heavily overdue (140 days overdue on a 31-day cycle, clamped to 1.0).

    Arithmetic:
    - criticality = 2 -> norm = (2-1)/4 = 0.25
    - defect_severity = 2 -> norm = (2-1)/4 = 0.25
    - due_date = 2026-06-01, last_done = 2026-05-01 (interval = 31 days)
      days overdue = 140 -> 140/31 > 1.0 -> clamped to 1.0
    - traffic_impact = 0.20
    - c_crit = 100 * 0.35 * 0.25 = 8.75
    - c_sev = 100 * 0.30 * 0.25 = 7.50
    - c_overdue = 100 * 0.20 * 1.00 = 20.00
    - c_traffic = 100 * 0.15 * 0.20 = 3.00
    - Expected score = 8.75 + 7.50 + 20.00 + 3.00 = 39.25, Band = MEDIUM
    """
    task = {
        "id": "T4",
        "criticality": 2,
        "defect_severity": 2,
        "due_date": "2026-06-01",
        "last_done_date": "2026-05-01",
        "traffic_impact": 0.20,
    }
    res = calculate_task_priority(task, today=TODAY)
    assert res.score == 39.25
    assert res.contributions.criticality == 8.75
    assert res.contributions.defect_severity == 7.50
    assert res.contributions.overdue_ratio == 20.00
    assert res.contributions.traffic_impact == 3.00
    assert res.priority_band == BAND_MEDIUM


def test_hand_calc_case_5_partial_overdue_high() -> None:
    """Case 5: Exactly 50% overdue (15 days overdue on 30-day interval).

    Arithmetic:
    - today = 2026-10-19, due_date = 2026-10-04 (15 days overdue)
    - last_done_date = 2026-09-04 (interval = 30 days)
    - overdue_ratio = 15 / 30 = 0.50
    - criticality = 4 -> norm = (4-1)/4 = 0.75
    - defect_severity = 4 -> norm = (4-1)/4 = 0.75
    - traffic_impact = 0.60
    - c_crit = 100 * 0.35 * 0.75 = 26.25
    - c_sev = 100 * 0.30 * 0.75 = 22.50
    - c_overdue = 100 * 0.20 * 0.50 = 10.00
    - c_traffic = 100 * 0.15 * 0.60 = 9.00
    - Expected score = 26.25 + 22.50 + 10.00 + 9.00 = 67.75, Band = HIGH
    """
    task = {
        "id": "T5",
        "criticality": 4,
        "defect_severity": 4,
        "due_date": "2026-10-04",
        "last_done_date": "2026-09-04",
        "traffic_impact": 0.60,
    }
    res = calculate_task_priority(task, today=TODAY)
    assert res.score == 67.75
    assert res.contributions.criticality == 26.25
    assert res.contributions.defect_severity == 22.50
    assert res.contributions.overdue_ratio == 10.00
    assert res.contributions.traffic_impact == 9.00
    assert res.priority_band == BAND_HIGH


def test_hand_calc_case_6_critical_track_defect_high() -> None:
    """Case 6: Realistic high-priority trunk route track defect (Case A).

    Arithmetic:
    - criticality = 5 (Trunk track) -> norm = 1.00
    - defect_severity = 4 (Weld crack) -> norm = (4-1)/4 = 0.75
    - due_date = 2026-10-10, last_done = 2026-08-11 (interval = 60 days)
      days overdue = 9 -> overdue_ratio = 9 / 60 = 0.15
    - traffic_impact = 0.80
    - c_crit = 100 * 0.35 * 1.00 = 35.00
    - c_sev = 100 * 0.30 * 0.75 = 22.50
    - c_overdue = 100 * 0.20 * 0.15 = 3.00
    - c_traffic = 100 * 0.15 * 0.80 = 12.00
    - Expected score = 35.00 + 22.50 + 3.00 + 12.00 = 72.50, Band = HIGH
    """
    task = {
        "id": "T6",
        "criticality": 5,
        "defect_severity": 4,
        "due_date": "2026-10-10",
        "last_done_date": "2026-08-11",
        "traffic_impact": 0.80,
    }
    res = calculate_task_priority(task, today=TODAY)
    assert res.score == 72.50
    assert res.contributions.criticality == 35.00
    assert res.contributions.defect_severity == 22.50
    assert res.contributions.overdue_ratio == 3.00
    assert res.contributions.traffic_impact == 12.00
    assert res.priority_band == BAND_HIGH


def test_hand_calc_case_7_urgent_derailment_risk_critical() -> None:
    """Case 7: Derailment risk crossing into CRITICAL priority band (Case B).

    Arithmetic:
    - criticality = 5 -> norm = 1.00
    - defect_severity = 5 -> norm = 1.00
    - due_date = 2026-10-09, last_done = 2026-09-09 (interval = 30 days)
      days overdue = 10 -> overdue_ratio = 10 / 30 = 0.333333
    - traffic_impact = 0.90
    - c_crit = 100 * 0.35 * 1.00 = 35.00
    - c_sev = 100 * 0.30 * 1.00 = 30.00
    - c_overdue = 100 * 0.20 * (10/30) = 6.6667
    - c_traffic = 100 * 0.15 * 0.90 = 13.50
    - Total raw = 35 + 30 + 6.6667 + 13.50 = 85.1667 -> 85.17
    - Expected score = 85.17, Band = CRITICAL
    """
    task = {
        "id": "T7",
        "criticality": 5,
        "defect_severity": 5,
        "due_date": "2026-10-09",
        "last_done_date": "2026-09-09",
        "traffic_impact": 0.90,
    }
    res = calculate_task_priority(task, today=TODAY)
    assert res.score == 85.17
    assert res.contributions.criticality == 35.00
    assert res.contributions.defect_severity == 30.00
    assert res.contributions.overdue_ratio == 6.67
    assert res.contributions.traffic_impact == 13.50
    assert res.priority_band == BAND_CRITICAL


def test_hand_calc_case_8_routine_washing_low() -> None:
    """Case 8: Low priority routine insulator washing on loop line (Case C).

    Arithmetic:
    - criticality = 2 -> norm = (2-1)/4 = 0.25
    - defect_severity = 1 -> norm = (1-1)/4 = 0.00
    - due_date = 2026-11-19 (not overdue) -> overdue_ratio = 0.0
    - traffic_impact = 0.20
    - c_crit = 100 * 0.35 * 0.25 = 8.75
    - c_sev = 100 * 0.30 * 0.00 = 0.00
    - c_overdue = 100 * 0.20 * 0.00 = 0.00
    - c_traffic = 100 * 0.15 * 0.20 = 3.00
    - Expected score = 8.75 + 0.00 + 0.00 + 3.00 = 11.75, Band = LOW
    """
    task = {
        "id": "T8",
        "criticality": 2,
        "defect_severity": 1,
        "due_date": "2026-11-19",
        "traffic_impact": 0.20,
    }
    res = calculate_task_priority(task, today=TODAY)
    assert res.score == 11.75
    assert res.contributions.criticality == 8.75
    assert res.contributions.defect_severity == 0.00
    assert res.contributions.overdue_ratio == 0.00
    assert res.contributions.traffic_impact == 3.00
    assert res.priority_band == BAND_LOW


def test_hand_calc_case_9_custom_weights() -> None:
    """Case 9: Custom weights configuration.

    Weights: crit=0.50, sev=0.30, overdue=0.10, traffic=0.10 (sum=1.0)
    Arithmetic:
    - c = 5 -> norm = 1.00
    - s = 4 -> norm = 0.75
    - overdue_ratio = 0.50 (due 2026-10-04, last 2026-09-04)
    - traffic = 0.40
    - c_crit = 100 * 0.50 * 1.00 = 50.00
    - c_sev = 100 * 0.30 * 0.75 = 22.50
    - c_overdue = 100 * 0.10 * 0.50 = 5.00
    - c_traffic = 100 * 0.10 * 0.40 = 4.00
    - Expected score = 50 + 22.50 + 5 + 4 = 81.50, Band = CRITICAL
    """
    custom_weights = PriorityWeights(
        criticality=0.50,
        defect_severity=0.30,
        overdue_ratio=0.10,
        traffic_impact=0.10,
    )
    task = {
        "id": "T9",
        "criticality": 5,
        "defect_severity": 4,
        "due_date": "2026-10-04",
        "last_done_date": "2026-09-04",
        "traffic_impact": 0.40,
    }
    res = calculate_task_priority(task, weights=custom_weights, today=TODAY)
    assert res.score == 81.50
    assert res.contributions.criticality == 50.00
    assert res.contributions.defect_severity == 22.50
    assert res.contributions.overdue_ratio == 5.00
    assert res.contributions.traffic_impact == 4.00
    assert res.priority_band == BAND_CRITICAL


# ==============================================================================
# WEIGHTS VALIDATION TESTS
# ==============================================================================


def test_weights_sum_validation() -> None:
    """Verify that weights not summing to 1.0 raise ValueError."""
    with pytest.raises(ValueError, match="must sum to 1.0"):
        PriorityWeights(
            criticality=0.4, defect_severity=0.4, overdue_ratio=0.3, traffic_impact=0.1
        ).validate()


def test_weights_negative_validation() -> None:
    """Verify that negative weight raises ValueError."""
    with pytest.raises(ValueError, match="cannot be negative"):
        PriorityWeights(
            criticality=-0.1, defect_severity=0.5, overdue_ratio=0.3, traffic_impact=0.3
        ).validate()


# ==============================================================================
# CONTRIBUTIONS SUM AND ORDERING STABILITY TESTS
# ==============================================================================


def test_contributions_sum_to_total() -> None:
    """Verify that for any scored task, sum of contributions equals score within rounding."""
    task = {
        "id": "TSUM",
        "criticality": 4,
        "defect_severity": 3,
        "due_date": "2026-10-15",
        "last_done_date": "2026-08-15",
        "traffic_impact": 0.72,
    }
    res = calculate_task_priority(task, today=TODAY)
    sum_contributions = (
        res.contributions.criticality
        + res.contributions.defect_severity
        + res.contributions.overdue_ratio
        + res.contributions.traffic_impact
    )
    assert abs(sum_contributions - res.score) <= 0.05


def test_ranking_and_ordering_stability() -> None:
    """Verify descending rank assignment and tie-breaking by deadline."""
    tasks = [
        {"id": "LOW", "criticality": 1, "defect_severity": 1, "deadline": 1000},
        {"id": "HIGH", "criticality": 5, "defect_severity": 5, "deadline": 2000},
        {"id": "MID1", "criticality": 3, "defect_severity": 3, "deadline": 500},
        {"id": "MID2", "criticality": 3, "defect_severity": 3, "deadline": 800},
    ]
    ranked = rank_tasks_by_priority(tasks, today=TODAY)
    assert [r.task_id for r in ranked] == ["HIGH", "MID1", "MID2", "LOW"]
    assert [r.rank for r in ranked] == [1, 2, 3, 4]


# ==============================================================================
# API ENDPOINT TESTS (GET /api/priority)
# ==============================================================================


def test_api_priority_endpoint(client: TestClient) -> None:
    """Verify GET /api/priority endpoint returns ranked tasks with breakdowns."""
    # Seed database first
    client.post("/api/seed", json={"seed": 42, "reset": True})

    res = client.get("/api/priority")
    assert res.status_code == 200
    data = res.json()

    assert data["total_tasks"] == 50
    assert len(data["tasks"]) == 50
    assert "CRITICAL" in data["band_counts"]
    assert "HIGH" in data["band_counts"]

    # Verify descending score order
    scores = [t["score"] for t in data["tasks"]]
    assert scores == sorted(scores, reverse=True)

    # First task has rank 1
    assert data["tasks"][0]["rank"] == 1
    # Check contribution fields exist
    first = data["tasks"][0]
    assert "criticality" in first["contributions"]
    assert "defect_severity" in first["contributions"]
    assert "overdue_ratio" in first["contributions"]
    assert "traffic_impact" in first["contributions"]


def test_api_priority_filters(client: TestClient) -> None:
    """Verify GET /api/priority with department and band filters."""
    client.post("/api/seed", json={"seed": 42, "reset": True})

    # Filter by department
    res_eng = client.get("/api/priority?department=ENGINEERING")
    assert res_eng.status_code == 200
    for t in res_eng.json()["tasks"]:
        assert t["department"] == "ENGINEERING"

    # Filter by priority_band
    res_crit = client.get("/api/priority?priority_band=CRITICAL")
    assert res_crit.status_code == 200
    for t in res_crit.json()["tasks"]:
        assert t["priority_band"] == "CRITICAL"


def test_api_priority_invalid_weights(client: TestClient) -> None:
    """Verify that invalid weights return HTTP 422 Unprocessable Entity."""
    res = client.get("/api/priority?weight_criticality=0.9&weight_severity=0.9")
    assert res.status_code == 422
    assert "must sum to 1.0" in res.json()["detail"]
