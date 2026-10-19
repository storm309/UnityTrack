"""Unit and integration tests for Section 3: Compatibility rules and bundling engine.

Verifies:
1. Positive and negative tests for each compatibility rule:
   - Geographic corridor match / mismatch
   - Section proximity (exact vs adjacent)
   - Feasible time window overlap and sufficiency
   - Department pairing rules (TRD+SNT, ENG+SNT, ENG+TRD, ENG+ENG)
   - Safety constraints (live-line vs heavy track possession)
   - Departmental crew capacity limits
2. Invariants:
   - No bundle candidate contains an incompatible pair (clique invariant)
   - Every bundle has a non-empty feasible window >= bundle duration
   - Parallel vs sequential duration aggregation math
   - Determinism across repeated runs
3. API Endpoints:
   - GET /api/bundles/candidates with filters
   - GET /api/bundles/check with explanation reasons
"""

from typing import Dict

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import create_app
from app.optimizer.bundling import (
    CONFLICT_CORRIDOR_MISMATCH,
    CONFLICT_CREW_CAPACITY_EXCEEDED,
    CONFLICT_SAFETY_LIVE_LINE,
    CONFLICT_SECTION_MISMATCH,
    CONFLICT_SECTION_NOT_ADJACENT,
    CONFLICT_WINDOW_DISJOINT,
    CONFLICT_WINDOW_TOO_SHORT,
    BundlingConfig,
    SectionInfo,
    TaskItem,
    check_pairwise_compatibility,
    compute_bundle_metrics,
    find_candidate_bundles,
)
from app.seed import seed_database

# Fixture setup
SAMPLE_SECTIONS: Dict[str, SectionInfo] = {
    "SEC-01": SectionInfo(id="SEC-01", corridor_id="CORR-01", name="Ghaziabad - Dadri", order_index=0),
    "SEC-02": SectionInfo(id="SEC-02", corridor_id="CORR-01", name="Dadri - Sikandrabad", order_index=1),
    "SEC-03": SectionInfo(id="SEC-03", corridor_id="CORR-01", name="Sikandrabad - Aligarh", order_index=2),
    "SEC-04": SectionInfo(id="SEC-04", corridor_id="CORR-02", name="Separate Corridor Sec", order_index=0),
}

CAPACITIES = {"ENGINEERING": 3, "TRACTION": 2, "SNT": 3}


def make_task(
    id: str,
    dept: str,
    sec_id: str = "SEC-01",
    corr_id: str = "CORR-01",
    asset: str = "Track",
    duration: int = 120,
    earliest: int = 0,
    deadline: int = 720,
    crew: int = 1,
    power_off: bool = False,
    track_block: bool = True,
    title: str = "Sample Task",
    priority_score: float = 75.0,
) -> TaskItem:
    """Helper to construct TaskItem instances for tests."""
    return TaskItem(
        id=id,
        title=title,
        department=dept,
        section_id=sec_id,
        corridor_id=corr_id,
        asset_type=asset,
        duration_min=duration,
        earliest_start=earliest,
        deadline=deadline,
        crew_needed=crew,
        requires_power_off=power_off,
        requires_track_block=track_block,
        priority_score=priority_score,
    )


# ---------------------------------------------------------------------------
# Rule 1: Geographic Corridor Match / Mismatch
# ---------------------------------------------------------------------------


def test_rule_corridor_match_positive() -> None:
    t1 = make_task("T1", "ENGINEERING", corr_id="CORR-01", sec_id="SEC-01")
    t2 = make_task("T2", "SNT", corr_id="CORR-01", sec_id="SEC-01")
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert res.conflict_code is None


def test_rule_corridor_mismatch_negative() -> None:
    t1 = make_task("T1", "ENGINEERING", corr_id="CORR-01", sec_id="SEC-01")
    t2 = make_task("T2", "SNT", corr_id="CORR-02", sec_id="SEC-04")
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is False
    assert res.conflict_code == CONFLICT_CORRIDOR_MISMATCH
    assert "different corridors" in (res.conflict_reason or "")


# ---------------------------------------------------------------------------
# Rule 2: Section Proximity (Exact vs Adjacent)
# ---------------------------------------------------------------------------


def test_rule_section_same_positive() -> None:
    t1 = make_task("T1", "TRACTION", sec_id="SEC-01")
    t2 = make_task("T2", "SNT", sec_id="SEC-01")
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert any("Same physical track section" in r for r in res.reasons)


def test_rule_section_different_negative_when_adjacent_disabled() -> None:
    t1 = make_task("T1", "TRACTION", sec_id="SEC-01")
    t2 = make_task("T2", "SNT", sec_id="SEC-02")
    cfg = BundlingConfig(allow_adjacent_sections=False)
    res = check_pairwise_compatibility(t1, t2, config=cfg, section_map=SAMPLE_SECTIONS)
    assert res.is_compatible is False
    assert res.conflict_code == CONFLICT_SECTION_MISMATCH


def test_rule_section_adjacent_positive_when_adjacent_enabled() -> None:
    # SEC-01 (order 0) and SEC-02 (order 1) are adjacent
    t1 = make_task("T1", "TRACTION", sec_id="SEC-01")
    t2 = make_task("T2", "SNT", sec_id="SEC-02")
    cfg = BundlingConfig(allow_adjacent_sections=True)
    res = check_pairwise_compatibility(t1, t2, config=cfg, section_map=SAMPLE_SECTIONS)
    assert res.is_compatible is True
    assert any("Adjacent sections" in r for r in res.reasons)


def test_rule_section_non_adjacent_negative_when_adjacent_enabled() -> None:
    # SEC-01 (order 0) and SEC-03 (order 2) -> abs(0 - 2) = 2 > 1
    t1 = make_task("T1", "TRACTION", sec_id="SEC-01")
    t2 = make_task("T2", "SNT", sec_id="SEC-03")
    cfg = BundlingConfig(allow_adjacent_sections=True)
    res = check_pairwise_compatibility(t1, t2, config=cfg, section_map=SAMPLE_SECTIONS)
    assert res.is_compatible is False
    assert res.conflict_code == CONFLICT_SECTION_NOT_ADJACENT


# ---------------------------------------------------------------------------
# Rule 3: Feasible Time Window Overlap
# ---------------------------------------------------------------------------


def test_rule_window_overlap_positive() -> None:
    # [100, 600] and [200, 800] -> overlap [200, 600] = 400 min >= 120 min duration
    t1 = make_task("T1", "TRACTION", earliest=100, deadline=600, duration=120)
    t2 = make_task("T2", "SNT", earliest=200, deadline=800, duration=90)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert res.combined_duration_min == 120  # parallel max(120, 90)


def test_rule_window_disjoint_negative() -> None:
    # [0, 300] and [400, 700] -> no overlap
    t1 = make_task("T1", "TRACTION", earliest=0, deadline=300)
    t2 = make_task("T2", "SNT", earliest=400, deadline=700)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is False
    assert res.conflict_code == CONFLICT_WINDOW_DISJOINT


def test_rule_window_insufficient_length_negative() -> None:
    # [100, 300] and [250, 500] -> overlap [250, 300] = 50 min. But max duration is 120 min!
    t1 = make_task("T1", "TRACTION", earliest=100, deadline=300, duration=120)
    t2 = make_task("T2", "SNT", earliest=250, deadline=500, duration=90)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is False
    assert res.conflict_code == CONFLICT_WINDOW_TOO_SHORT
    assert "insufficient" in (res.conflict_reason or "")


# ---------------------------------------------------------------------------
# Rule 4: Department Pairing & Safety Rules
# ---------------------------------------------------------------------------


def test_department_pairing_trd_and_snt_parallel() -> None:
    # TRD (150 min) + SNT (90 min) -> parallel duration = max(150, 90) = 150 min
    # Disruption savings = (150 + 90) - 150 = 90 min!
    t1 = make_task("T1", "TRACTION", asset="Cantilever", duration=150, power_off=True)
    t2 = make_task("T2", "SNT", asset="Point Machine", duration=90, power_off=False)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert res.execution_mode == "PARALLEL"
    assert res.combined_duration_min == 150
    assert res.disruption_savings_min == 90
    assert res.requires_power_off is True


def test_department_pairing_eng_and_snt_parallel() -> None:
    # ENG inspection (120 min) + SNT signal replacement (90 min) -> parallel
    t1 = make_task("T1", "ENGINEERING", asset="USFD Testing", duration=120, title="Ultrasonic Flaw")
    t2 = make_task("T2", "SNT", asset="Signal Aspect", duration=90, title="Color Light Replacement")
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert res.execution_mode == "PARALLEL"
    assert res.combined_duration_min == 120
    assert res.disruption_savings_min == 90


def test_department_pairing_eng_heavy_machine_and_snt_track_circuit_sequential() -> None:
    # Heavy track tamping vs Track circuit testing -> SEQUENTIAL
    t1 = make_task("T1", "ENGINEERING", asset="Ballast", duration=180, title="Ballast Tamping Machine")
    t2 = make_task("T2", "SNT", asset="Track Circuit", duration=60, title="Track Circuit Lead Testing")
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert res.execution_mode == "SEQUENTIAL"
    assert res.combined_duration_min == 240  # 180 + 60
    assert res.disruption_savings_min == 0


def test_department_pairing_eng_and_trd_power_off_parallel() -> None:
    # ENG civil work (150 min) + TRD catenary work (120 min) with power off
    t1 = make_task("T1", "ENGINEERING", asset="Track", duration=150, power_off=False)
    t2 = make_task("T2", "TRACTION", asset="OHE Contact Wire", duration=120, power_off=True)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert res.execution_mode == "PARALLEL"
    assert res.combined_duration_min == 150
    assert res.requires_power_off is True


def test_department_pairing_eng_and_trd_live_line_safety_conflict() -> None:
    # If TRD attempts live-line patrol without power-off during heavy track possession
    t1 = make_task("T1", "ENGINEERING", asset="Track", power_off=False, track_block=True)
    t2 = make_task("T2", "TRACTION", asset="Live Wire Patrol", power_off=False, track_block=False)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is False
    assert res.conflict_code == CONFLICT_SAFETY_LIVE_LINE


def test_same_department_eng_sequential() -> None:
    # Two civil engineering tasks on the same track section must run sequentially
    t1 = make_task("T1", "ENGINEERING", asset="Track", duration=120)
    t2 = make_task("T2", "ENGINEERING", asset="Track", duration=90)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert res.execution_mode == "SEQUENTIAL"
    assert res.combined_duration_min == 210  # 120 + 90
    assert res.disruption_savings_min == 0


def test_same_department_snt_distinct_assets_parallel() -> None:
    # Point Machine (90 min) vs Signal Aspect (120 min) -> parallel
    t1 = make_task("T1", "SNT", asset="Point Machine", duration=90)
    t2 = make_task("T2", "SNT", asset="Signal Aspect", duration=120)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True
    assert res.execution_mode == "PARALLEL"
    assert res.combined_duration_min == 120


# ---------------------------------------------------------------------------
# Rule 5: Resource Capacity Limits
# ---------------------------------------------------------------------------


def test_resource_capacity_positive_within_limit() -> None:
    # 2 ENG tasks requiring 1 + 2 = 3 crews. Capacity is 3 -> Compatible
    t1 = make_task("T1", "ENGINEERING", crew=1, deadline=1000)
    t2 = make_task("T2", "ENGINEERING", crew=2, deadline=1000)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is True


def test_resource_capacity_negative_exceeded() -> None:
    # 2 ENG tasks requiring 2 + 2 = 4 crews. Capacity is 3 -> INCOMPATIBLE
    t1 = make_task("T1", "ENGINEERING", crew=2, deadline=1000)
    t2 = make_task("T2", "ENGINEERING", crew=2, deadline=1000)
    res = check_pairwise_compatibility(t1, t2, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    assert res.is_compatible is False
    assert res.conflict_code == CONFLICT_CREW_CAPACITY_EXCEEDED
    assert "exceeds" in (res.conflict_reason or "")


# ---------------------------------------------------------------------------
# Multi-Task Candidate Bundle Invariants & Cliques
# ---------------------------------------------------------------------------


def test_bundle_metrics_hybrid_aggregation() -> None:
    # 2 ENG sequential (120 + 90 = 210 min), 1 SNT parallel (60 min), 1 TRD parallel (180 min)
    # Total duration = max(210 [ENG], 180 [TRD], 60 [SNT]) = 210 min
    t_eng1 = make_task("E1", "ENGINEERING", duration=120)
    t_eng2 = make_task("E2", "ENGINEERING", duration=90)
    t_snt = make_task("S1", "SNT", duration=60)
    t_trd = make_task("R1", "TRACTION", duration=180, power_off=True)

    dur, mode, savings, eff, pwr, trk, crews = compute_bundle_metrics(
        [t_eng1, t_eng2, t_snt, t_trd]
    )
    assert dur == 210
    assert mode == "HYBRID"
    assert savings == (120 + 90 + 60 + 180) - 210  # 450 - 210 = 240
    assert pwr is True
    assert trk is True
    assert crews == {"ENGINEERING": 2, "SNT": 1, "TRACTION": 1}


def test_find_candidate_bundles_clique_pairwise_invariant() -> None:
    """Verify that every multi-task candidate bundle is a valid clique with non-empty window."""
    t1 = make_task("T1", "TRACTION", sec_id="SEC-01", duration=120, power_off=True)
    t2 = make_task("T2", "SNT", sec_id="SEC-01", asset="Point Machine", duration=90)
    t3 = make_task("T3", "ENGINEERING", sec_id="SEC-01", asset="USFD", duration=120)

    # Incompatible task (different corridor)
    t_incompat = make_task("T4", "SNT", corr_id="CORR-02", sec_id="SEC-04")

    all_tasks = [t1, t2, t3, t_incompat]
    candidates = find_candidate_bundles(
        all_tasks,
        section_map=SAMPLE_SECTIONS,
        crew_capacities=CAPACITIES,
        max_bundle_size=3,
    )

    assert len(candidates) > 0
    task_lookup = {t.id: t for t in all_tasks}

    for bundle in candidates:
        # Invariant 1: No candidate includes incompatible task T4
        assert "T4" not in bundle.task_ids

        # Invariant 2: Pairwise compatibility between every single pair in the bundle
        b_tasks = [task_lookup[tid] for tid in bundle.task_ids]
        for i in range(len(b_tasks)):
            for j in range(i + 1, len(b_tasks)):
                pair_res = check_pairwise_compatibility(
                    b_tasks[i],
                    b_tasks[j],
                    section_map=SAMPLE_SECTIONS,
                    crew_capacities=CAPACITIES,
                )
                assert pair_res.is_compatible is True, (
                    f"Pair ({b_tasks[i].id}, {b_tasks[j].id}) in bundle {bundle.bundle_id} is incompatible: "
                    f"{pair_res.conflict_reason}"
                )

        # Invariant 3: Feasible window intersection is strictly >= bundle duration
        window_len = bundle.deadline - bundle.earliest_start
        assert window_len >= bundle.duration_min

        # Invariant 4: Disruption savings formula verified
        raw_sum = sum(t.duration_min for t in b_tasks)
        assert bundle.disruption_savings_min == raw_sum - bundle.duration_min


def test_bundling_determinism() -> None:
    """Running bundle generation multiple times on identical input yields identical outputs."""
    t1 = make_task("T1", "TRACTION", sec_id="SEC-01", duration=120, power_off=True)
    t2 = make_task("T2", "SNT", sec_id="SEC-01", asset="Point Machine", duration=90)
    t3 = make_task("T3", "ENGINEERING", sec_id="SEC-01", asset="USFD", duration=120)
    tasks = [t1, t2, t3]

    run1 = find_candidate_bundles(tasks, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    run2 = find_candidate_bundles(tasks, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)
    run3 = find_candidate_bundles(tasks, section_map=SAMPLE_SECTIONS, crew_capacities=CAPACITIES)

    assert [b.bundle_id for b in run1] == [b.bundle_id for b in run2] == [b.bundle_id for b in run3]
    assert [b.duration_min for b in run1] == [b.duration_min for b in run2]
    assert [b.disruption_savings_min for b in run1] == [b.disruption_savings_min for b in run2]


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    from app.database import SessionLocal

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db, seed=42, reset=True)
    finally:
        db.close()
    app = create_app()
    return TestClient(app)


def test_api_candidate_bundles_endpoint(api_client: TestClient) -> None:
    res = api_client.get("/api/bundles/candidates")
    assert res.status_code == 200
    data = res.json()
    assert "total_candidates" in data
    assert data["total_candidates"] > 0
    assert data["cross_departmental_count"] > 0
    assert data["total_potential_savings_min"] > 0
    assert len(data["candidates"]) == data["total_candidates"]

    # Verify first candidate structure
    c0 = data["candidates"][0]
    assert "bundle_id" in c0
    assert "task_ids" in c0
    assert len(c0["task_ids"]) >= 2
    assert "execution_mode" in c0
    assert c0["duration_min"] > 0
    assert "compatibility_reasons" in c0
    assert len(c0["compatibility_reasons"]) > 0


def test_api_candidate_bundles_filter_cross_department(api_client: TestClient) -> None:
    res = api_client.get("/api/bundles/candidates?cross_department_only=true")
    assert res.status_code == 200
    data = res.json()
    for b in data["candidates"]:
        assert b["is_cross_departmental"] is True
        assert len(b["departments"]) >= 2


def test_api_candidate_bundles_filter_department(api_client: TestClient) -> None:
    res = api_client.get("/api/bundles/candidates?department=TRACTION")
    assert res.status_code == 200
    data = res.json()
    for b in data["candidates"]:
        assert "TRACTION" in b["departments"]


def test_api_pairwise_check_endpoint(api_client: TestClient) -> None:
    # Query tasks to get two valid task IDs
    tasks_res = api_client.get("/api/tasks?limit=5")
    assert tasks_res.status_code == 200
    tasks = tasks_res.json()
    assert len(tasks) >= 2
    t1_id = tasks[0]["id"]
    t2_id = tasks[1]["id"]

    res = api_client.get(f"/api/bundles/check?task_a_id={t1_id}&task_b_id={t2_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["task_a_id"] == t1_id
    assert data["task_b_id"] == t2_id
    assert "is_compatible" in data
    assert "reasons" in data


def test_api_pairwise_check_not_found(api_client: TestClient) -> None:
    res = api_client.get("/api/bundles/check?task_a_id=NON_EXISTENT&task_b_id=TASK-001")
    assert res.status_code == 404
