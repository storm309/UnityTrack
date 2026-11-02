"""Comprehensive test suite for Section 6 Explanation Generator.

Verifies:
1. Strict Numerical Traceability: Every single number in each explanation matches
   the exact solver/baseline/priority metrics.
2. Template Coverage: All template variants (plan recommendation, multi-department bundle,
   single-task block, priority attribution, delay root cause) are thoroughly tested.
3. No empty strings or unformatted template placeholders (e.g. no '{', '}').
4. Anti-hallucination verification: Test that verify_numbers_match_facts accepts true facts
   and strictly rejects hallucinated numbers.
5. REST API Integration: GET /api/plans/{id}/explanations returns 200 OK with valid schema.
"""

from typing import Set

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import create_app
from app.optimizer.baseline import BaselinePlanResult
from app.optimizer.bundling import SectionInfo, TaskItem
from app.optimizer.explanations import (
    explain_bundle,
    explain_plan_recommendation,
    explain_task_delay,
    explain_task_priority,
    extract_numbers_from_text,
    verify_numbers_match_facts,
)
from app.optimizer.validator import ScheduledBlock, ScheduledTaskAssignment
from app.seed import seed_database


@pytest.fixture(scope="module")
def api_client() -> TestClient:
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


def make_dummy_task(
    t_id: str = "T-01",
    dept: str = "ENGINEERING",
    sec_id: str = "SEC-01",
    duration: int = 120,
    deadline: int = 1440,
    crew: int = 2,
    crit: int = 4,
    sev: int = 5,
    traffic: float = 0.8,
) -> TaskItem:
    return TaskItem(
        id=t_id,
        title=f"Sample Track Work {t_id}",
        department=dept,
        section_id=sec_id,
        corridor_id="CORR-01",
        asset_type="Track",
        duration_min=duration,
        earliest_start=0,
        deadline=deadline,
        crew_needed=crew,
        criticality=crit,
        defect_severity=sev,
        traffic_impact=traffic,
        due_date="2026-11-05",
        last_done_date="2026-10-01",
        priority_score=85.0,
    )


def test_plan_recommendation_numbers_strictly_match_metrics() -> None:
    """Verify that every number in plan recommendation text strictly matches baseline & optimizer metrics."""
    baseline = BaselinePlanResult(
        blocks=[],
        task_assignments=[],
        total_blocks=50,
        total_disruption_minutes=7500,
        scheduled_tasks_count=50,
        delayed_tasks_count=3,
        total_delay_minutes=180,
    )

    rec = explain_plan_recommendation(
        optimized_blocks_count=42,
        optimized_disruption_min=6400,
        cross_dept_blocks_count=7,
        delayed_tasks_count=0,
        tasks_scheduled_count=50,
        baseline=baseline,
    )

    assert rec.baseline_blocks == 50
    assert rec.optimized_blocks == 42
    assert rec.blocks_saved == 8
    assert rec.block_reduction_pct == 16.0
    assert rec.baseline_disruption_min == 7500
    assert rec.optimized_disruption_min == 6400
    assert rec.disruption_savings_min == 1100
    assert rec.disruption_savings_pct == 14.7

    # Collect expected numbers
    expected_numbers: Set[float] = {
        50.0, 42.0, 8.0, 16.0, 7500.0, 6400.0, 1100.0, 14.7, 7.0, 0.0, 3.0,
        round(7500 / 60, 1), round(6400 / 60, 1),
    }

    # Verify headline
    headline_nums = extract_numbers_from_text(rec.headline)
    for n in headline_nums:
        assert any(abs(n - exp) <= 0.1 for exp in expected_numbers), f"Unexpected number {n} in headline: {rec.headline}"

    # Verify summary
    summary_nums = extract_numbers_from_text(rec.summary)
    for n in summary_nums:
        assert any(abs(n - exp) <= 0.1 for exp in expected_numbers), f"Unexpected number {n} in summary: {rec.summary}"

    # Verify no unformatted placeholders
    assert "{" not in rec.headline and "}" not in rec.headline
    assert "{" not in rec.summary and "}" not in rec.summary
    for bullet in rec.detailed_bullets:
        assert "{" not in bullet and "}" not in bullet
        assert len(bullet) > 10


def test_bundle_explanation_single_and_multi_task() -> None:
    """Verify bundle explanations for both single-task and multi-department joint blocks."""
    t1 = make_dummy_task("T-ENG-1", dept="ENGINEERING", duration=120)
    t2 = make_dummy_task("T-TRD-1", dept="TRACTION", duration=90)
    task_map = {t1.id: t1, t2.id: t2}
    sec_map = {"SEC-01": SectionInfo(id="SEC-01", corridor_id="CORR-01", name="Delhi - Ghaziabad", order_index=1)}

    # Multi-task cross-departmental block
    multi_block = ScheduledBlock(
        block_id="OPT-BLK-001",
        section_id="SEC-01",
        start_min=60,
        end_min=180,
        duration_min=120,
        task_ids=["T-ENG-1", "T-TRD-1"],
        departments=["ENGINEERING", "TRACTION"],
        requires_power_off=True,
        requires_track_block=True,
    )

    exp_multi = explain_bundle(multi_block, tasks_map=task_map, sections_map=sec_map)
    assert exp_multi.is_cross_departmental is True
    assert exp_multi.task_count == 2
    assert exp_multi.sum_individual_durations == 210  # 120 + 90
    assert exp_multi.disruption_savings_min == 90     # 210 - 120
    assert "Delhi - Ghaziabad" in exp_multi.justification
    assert "saving 90 minutes" in exp_multi.justification
    assert "{" not in exp_multi.justification and "}" not in exp_multi.justification

    # Single-task block
    single_block = ScheduledBlock(
        block_id="OPT-BLK-002",
        section_id="SEC-01",
        start_min=300,
        end_min=420,
        duration_min=120,
        task_ids=["T-ENG-1"],
        departments=["ENGINEERING"],
        requires_power_off=False,
        requires_track_block=True,
    )
    exp_single = explain_bundle(single_block, tasks_map=task_map, sections_map=sec_map)
    assert exp_single.is_cross_departmental is False
    assert exp_single.task_count == 1
    assert exp_single.disruption_savings_min == 0
    assert "Dedicated block" in exp_single.justification


def test_priority_explanation_mathematical_decomposition() -> None:
    """Verify priority explanation factor breakdown sums exactly to the priority score."""
    task = make_dummy_task(crit=5, sev=4, traffic=0.8)
    exp = explain_task_priority(task)

    assert exp.priority_band in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert len(exp.top_contributing_factors) == 4

    # Sum of factor point contributions must equal total priority score within floating tolerance
    factor_points_sum = sum(f.points_contributed for f in exp.top_contributing_factors)
    assert abs(factor_points_sum - exp.priority_score) <= 0.15

    # Check that text contains accurate points
    assert "classified in priority band" in exp.summary
    assert f"{exp.priority_score:.1f}" in exp.summary
    assert "{" not in exp.summary and "}" not in exp.summary


def test_delay_explanation_binding_constraints() -> None:
    """Verify delay explanation accurately reports delay duration and binding constraints."""
    task = make_dummy_task("T-DELAY", dept="ENGINEERING", duration=120, deadline=600, crew=4)
    sec_map = {"SEC-01": SectionInfo(id="SEC-01", corridor_id="CORR-01", name="Section 1", order_index=1)}

    assignment = ScheduledTaskAssignment(
        task_id=task.id,
        block_id="BLK-01",
        section_id="SEC-01",
        start_min=700,
        duration_min=120,
        finish_min=820,
        department="ENGINEERING",
        is_delayed=True,
        delay_minutes=220,  # 820 - 600
    )

    exp = explain_task_delay(
        assignment=assignment,
        task=task,
        sections_map=sec_map,
        crew_capacities={"ENGINEERING": 4},
    )

    assert exp.delay_minutes == 220
    assert exp.binding_constraint in (
        "RESOURCE_CREW_BOTTLENECK",
        "ENGINEERING_SEQUENTIAL_CHAIN",
        "TIMETABLE_TRAFFIC_SATURATION",
    )
    assert "exceeding its deadline of minute 600 by 220 minutes" in exp.root_cause_analysis
    assert "{" not in exp.root_cause_analysis and "}" not in exp.root_cause_analysis


def test_anti_hallucination_number_verifier() -> None:
    """Verify that verify_numbers_match_facts accepts valid text and rejects fabricated numbers."""
    allowed: Set[float] = {42.0, 50.0, 8.0, 16.0, 6400.0, 7500.0, 1100.0}

    valid_text = "The plan reduced 50 blocks to 42 blocks, saving 8 blocks (16.0% reduction)."
    assert verify_numbers_match_facts(valid_text, allowed) is True

    # Hallucinated text introduces a non-existent number 999.0
    invalid_text = "The plan miraculously saved 999 blocks across the railway."
    assert verify_numbers_match_facts(invalid_text, allowed) is False


def test_api_get_plan_explanations(api_client: TestClient) -> None:
    """Integration test: Generate a plan and retrieve its comprehensive explanations."""
    # 1. Generate plan
    gen_resp = api_client.post(
        "/api/plans/generate",
        json={"name": "Explanations Test Plan", "time_limit_seconds": 15.0},
    )
    assert gen_resp.status_code == 201
    plan_id = gen_resp.json()["id"]

    # 2. Fetch explanations
    exp_resp = api_client.get(f"/api/plans/{plan_id}/explanations")
    assert exp_resp.status_code == 200
    data = exp_resp.json()

    # Verify structure
    assert data["plan_id"] == plan_id
    assert "recommendation" in data
    assert "headline" in data["recommendation"]
    assert "summary" in data["recommendation"]
    assert len(data["recommendation"]["key_tradeoffs"]) > 0

    assert "bundle_explanations" in data
    assert len(data["bundle_explanations"]) > 0

    # Verify every bundle has valid text
    for b in data["bundle_explanations"]:
        assert len(b["justification"]) > 0
        assert "{" not in b["justification"] and "}" not in b["justification"]
        assert len(b["safety_compatibility_notes"]) > 0

    assert "priority_explanations" in data
    assert len(data["priority_explanations"]) > 0
    first_p = data["priority_explanations"][0]
    assert len(first_p["top_contributing_factors"]) == 4

    assert "numerical_facts" in data
    assert data["numerical_facts"]["total_blocks"] > 0
