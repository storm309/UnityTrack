"""API endpoints for candidate bundle generation and compatibility checking."""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import Resource, Section, Task
from app.optimizer.bundling import (
    BundlingConfig,
    SectionInfo,
    TaskItem,
    check_pairwise_compatibility,
    find_candidate_bundles,
)
from app.optimizer.priority import calculate_task_priority
from app.schemas.bundle import (
    BundleCandidateSchema,
    CandidateBundlesListResponse,
    PairwiseCompatibilityResponse,
    TaskSummarySchema,
)

router = APIRouter(prefix="/api/bundles", tags=["bundles"])


def _build_task_item(t: Task, corridor_id: str) -> TaskItem:
    """Convert a database Task into an optimizer TaskItem with priority score."""
    priority_res = calculate_task_priority(
        {
            "id": t.id,
            "criticality": t.criticality,
            "defect_severity": t.defect_severity,
            "due_date": t.due_date,
            "last_done_date": t.last_done_date,
            "traffic_impact": t.traffic_impact,
        }
    )
    return TaskItem(
        id=t.id,
        title=t.title,
        department=t.department,
        section_id=t.section_id,
        corridor_id=corridor_id,
        asset_type=t.asset_type,
        duration_min=t.duration_min,
        earliest_start=t.earliest_start,
        deadline=t.deadline,
        crew_needed=t.crew_needed,
        requires_power_off=t.requires_power_off,
        requires_track_block=t.requires_track_block,
        criticality=t.criticality,
        defect_severity=t.defect_severity,
        priority_score=priority_res.score,
    )


@router.get(
    "/candidates",
    response_model=CandidateBundlesListResponse,
    summary="Get candidate task bundles that can share a maintenance block",
)
def get_candidate_bundles(
    corridor_id: Optional[str] = Query(default=None, description="Filter bundles by corridor ID"),
    section_id: Optional[str] = Query(default=None, description="Filter bundles by section ID"),
    department: Optional[str] = Query(
        default=None, description="Filter bundles containing this department"
    ),
    cross_department_only: bool = Query(
        default=False, description="Return only cross-departmental bundles"
    ),
    max_bundle_size: int = Query(
        default=3, ge=2, le=4, description="Maximum number of tasks per bundle"
    ),
    allow_adjacent_sections: bool = Query(
        default=False, description="Allow bundling across adjacent physical sections"
    ),
    db: Session = Depends(get_db),
) -> CandidateBundlesListResponse:
    """Discover and return all candidate task bundles respecting compatibility rules.

    Rules applied:
    - Geographic: Same corridor; same section (or adjacent if enabled).
    - Temporal: Overlapping feasible windows wide enough for bundle duration.
    - Department & Safety Matrix: TRD+SNT parallel, ENG+SNT parallel/sequential, ENG+TRD power-off safe.
    - Resource capacity: Combined departmental crew does not exceed window limits.
    """
    # 1. Fetch Section metadata for section mapping
    sections = db.query(Section).all()
    section_map: Dict[str, SectionInfo] = {
        s.id: SectionInfo(
            id=s.id,
            corridor_id=s.corridor_id,
            name=s.name,
            order_index=s.order_index,
        )
        for s in sections
    }

    # 2. Fetch Department Crew Capacities
    resources = db.query(Resource).all()
    crew_capacities: Dict[str, int] = {
        r.department: r.capacity_per_window for r in resources
    }
    if not crew_capacities:
        crew_capacities = {"ENGINEERING": 3, "TRACTION": 2, "SNT": 3}

    # 3. Fetch Tasks
    query = db.query(Task).filter(Task.status == "PENDING")
    if section_id:
        query = query.filter(Task.section_id == section_id)

    db_tasks = query.all()
    if len(db_tasks) < 2:
        return CandidateBundlesListResponse(
            total_candidates=0,
            cross_departmental_count=0,
            total_potential_savings_min=0,
            candidates=[],
        )

    # Convert to pure optimizer TaskItems
    task_items: List[TaskItem] = []
    for t in db_tasks:
        sec = section_map.get(t.section_id)
        c_id = sec.corridor_id if sec else "CORR-01"
        if corridor_id and c_id != corridor_id:
            continue
        task_items.append(_build_task_item(t, corridor_id=c_id))

    # 4. Run Optimizer Bundling Engine
    cfg = BundlingConfig(
        allow_adjacent_sections=allow_adjacent_sections,
        max_bundle_size=max_bundle_size,
        default_crew_capacities=crew_capacities,
    )

    candidates = find_candidate_bundles(
        tasks=task_items,
        config=cfg,
        section_map=section_map,
        crew_capacities=crew_capacities,
        max_bundle_size=max_bundle_size,
    )

    # 5. Apply filters
    filtered = candidates
    if cross_department_only:
        filtered = [c for c in filtered if c.is_cross_departmental]
    if department:
        target_dept = department.upper()
        filtered = [c for c in filtered if target_dept in c.departments]
    if section_id:
        filtered = [c for c in filtered if c.section_id == section_id]

    cross_count = sum(1 for c in filtered if c.is_cross_departmental)
    total_savings = sum(c.disruption_savings_min for c in filtered)

    # 6. Format Response
    candidate_schemas = [
        BundleCandidateSchema(
            bundle_id=c.bundle_id,
            task_ids=c.task_ids,
            section_id=c.section_id,
            corridor_id=c.corridor_id,
            departments=c.departments,
            is_cross_departmental=c.is_cross_departmental,
            execution_mode=c.execution_mode,
            duration_min=c.duration_min,
            disruption_savings_min=c.disruption_savings_min,
            efficiency_gain_pct=c.efficiency_gain_pct,
            earliest_start=c.earliest_start,
            deadline=c.deadline,
            feasibility_window_min=c.feasibility_window_min,
            requires_power_off=c.requires_power_off,
            requires_track_block=c.requires_track_block,
            crew_needed_by_dept=c.crew_needed_by_dept,
            combined_priority_score=c.combined_priority_score,
            compatibility_reasons=c.compatibility_reasons,
            tasks_summary=[
                TaskSummarySchema(
                    id=t["id"],
                    title=t["title"],
                    department=t["department"],
                    asset_type=t["asset_type"],
                    duration_min=t["duration_min"],
                    priority_score=t["priority_score"],
                )
                for t in c.tasks_summary
            ],
        )
        for c in filtered
    ]

    return CandidateBundlesListResponse(
        total_candidates=len(candidate_schemas),
        cross_departmental_count=cross_count,
        total_potential_savings_min=total_savings,
        candidates=candidate_schemas,
    )


@router.get(
    "/check",
    response_model=PairwiseCompatibilityResponse,
    summary="Check pairwise compatibility between two specific tasks",
)
def check_tasks_compatibility(
    task_a_id: str = Query(..., description="First task ID"),
    task_b_id: str = Query(..., description="Second task ID"),
    allow_adjacent_sections: bool = Query(
        default=False, description="Allow bundling across adjacent physical sections"
    ),
    db: Session = Depends(get_db),
) -> PairwiseCompatibilityResponse:
    """Evaluate pairwise compatibility between two tasks with exact explainability."""
    task_a = db.query(Task).filter(Task.id == task_a_id).first()
    if not task_a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_a_id}' not found",
        )

    task_b = db.query(Task).filter(Task.id == task_b_id).first()
    if not task_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_b_id}' not found",
        )

    sections = db.query(Section).all()
    section_map = {
        s.id: SectionInfo(
            id=s.id,
            corridor_id=s.corridor_id,
            name=s.name,
            order_index=s.order_index,
        )
        for s in sections
    }

    resources = db.query(Resource).all()
    crew_capacities = {r.department: r.capacity_per_window for r in resources}
    if not crew_capacities:
        crew_capacities = {"ENGINEERING": 3, "TRACTION": 2, "SNT": 3}

    sec_a = section_map.get(task_a.section_id)
    sec_b = section_map.get(task_b.section_id)
    corridor_a = sec_a.corridor_id if sec_a else "CORR-01"
    corridor_b = sec_b.corridor_id if sec_b else "CORR-01"

    item_a = _build_task_item(task_a, corridor_id=corridor_a)
    item_b = _build_task_item(task_b, corridor_id=corridor_b)

    cfg = BundlingConfig(
        allow_adjacent_sections=allow_adjacent_sections,
        default_crew_capacities=crew_capacities,
    )

    result = check_pairwise_compatibility(
        task_a=item_a,
        task_b=item_b,
        config=cfg,
        section_map=section_map,
        crew_capacities=crew_capacities,
    )

    return PairwiseCompatibilityResponse(
        task_a_id=task_a_id,
        task_b_id=task_b_id,
        is_compatible=result.is_compatible,
        conflict_code=result.conflict_code,
        conflict_reason=result.conflict_reason,
        execution_mode=result.execution_mode,
        combined_duration_min=result.combined_duration_min,
        disruption_savings_min=result.disruption_savings_min,
        requires_power_off=result.requires_power_off,
        requires_track_block=result.requires_track_block,
        reasons=result.reasons,
    )
