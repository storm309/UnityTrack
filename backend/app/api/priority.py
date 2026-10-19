from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import Task
from app.optimizer.priority import (
    PriorityWeights,
    rank_tasks_by_priority,
)
from app.schemas.priority import (
    FactorContributionsSchema,
    PriorityItemResponse,
    PriorityListResponse,
    PriorityWeightsInput,
)

router = APIRouter(prefix="/api/priority", tags=["priority"])


@router.get(
    "",
    response_model=PriorityListResponse,
    summary="Get ranked tasks with explainable priority scores",
)
def get_priority_ranking(
    weight_criticality: float = Query(
        default=0.35, ge=0.0, le=1.0, description="Weight for criticality"
    ),
    weight_severity: float = Query(
        default=0.30, ge=0.0, le=1.0, description="Weight for defect severity"
    ),
    weight_overdue: float = Query(
        default=0.20, ge=0.0, le=1.0, description="Weight for overdue ratio"
    ),
    weight_traffic: float = Query(
        default=0.15, ge=0.0, le=1.0, description="Weight for traffic impact"
    ),
    department: Optional[str] = Query(default=None, description="Filter by department"),
    section_id: Optional[str] = Query(default=None, description="Filter by section ID"),
    priority_band: Optional[str] = Query(
        default=None, description="Filter by priority band: CRITICAL | HIGH | MEDIUM | LOW"
    ),
    db: Session = Depends(get_db),
) -> PriorityListResponse:
    """Compute explainable multi-factor priority scores for maintenance tasks.

    Formula:
      score = 100 * (0.35*criticality_norm + 0.30*severity_norm + 0.20*overdue_ratio + 0.15*traffic_impact)
    All factors normalized to [0, 1]. Total score strictly in [0, 100].
    """
    # 1. Validate weights sum to 1.0
    try:
        weights = PriorityWeights(
            criticality=weight_criticality,
            defect_severity=weight_severity,
            overdue_ratio=weight_overdue,
            traffic_impact=weight_traffic,
        )
        weights.validate()
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        ) from err

    # 2. Fetch tasks from database
    query = db.query(Task)
    if department:
        query = query.filter(Task.department == department.upper())
    if section_id:
        query = query.filter(Task.section_id == section_id)

    db_tasks = query.all()
    if not db_tasks:
        return PriorityListResponse(
            total_tasks=0,
            weights_used=PriorityWeightsInput(
                criticality=weight_criticality,
                defect_severity=weight_severity,
                overdue_ratio=weight_overdue,
                traffic_impact=weight_traffic,
            ),
            band_counts={"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            tasks=[],
        )

    # 3. Convert SQLAlchemy models to dicts for pure-python scoring engine
    raw_tasks = [
        {
            "id": t.id,
            "title": t.title,
            "department": t.department,
            "section_id": t.section_id,
            "criticality": t.criticality,
            "defect_severity": t.defect_severity,
            "due_date": t.due_date,
            "last_done_date": t.last_done_date,
            "traffic_impact": t.traffic_impact,
            "duration_min": t.duration_min,
            "earliest_start": t.earliest_start,
            "deadline": t.deadline,
        }
        for t in db_tasks
    ]

    # 4. Compute ranking using decoupled pure-python optimizer module
    ranked_results = rank_tasks_by_priority(raw_tasks, weights=weights)

    task_map = {t["id"]: t for t in raw_tasks}
    band_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    items: list[PriorityItemResponse] = []

    for res in ranked_results:
        band_counts[res.priority_band] = band_counts.get(res.priority_band, 0) + 1

        # Apply priority_band filter if specified
        if priority_band and res.priority_band != priority_band.upper():
            continue

        orig = task_map.get(res.task_id, {})
        items.append(
            PriorityItemResponse(
                task_id=res.task_id,
                title=str(orig.get("title", "")),
                department=str(orig.get("department", "")),
                section_id=str(orig.get("section_id", "")),
                score=res.score,
                rank=res.rank,
                priority_band=res.priority_band,
                contributions=FactorContributionsSchema(
                    criticality=res.contributions.criticality,
                    defect_severity=res.contributions.defect_severity,
                    overdue_ratio=res.contributions.overdue_ratio,
                    traffic_impact=res.contributions.traffic_impact,
                ),
                factors_normalized=res.factors_normalized,
                raw_factors={
                    "criticality": orig.get("criticality"),
                    "defect_severity": orig.get("defect_severity"),
                    "due_date": orig.get("due_date"),
                    "last_done_date": orig.get("last_done_date"),
                    "traffic_impact": orig.get("traffic_impact"),
                },
            )
        )

    return PriorityListResponse(
        total_tasks=len(items),
        weights_used=PriorityWeightsInput(
            criticality=weight_criticality,
            defect_severity=weight_severity,
            overdue_ratio=weight_overdue,
            traffic_impact=weight_traffic,
        ),
        band_counts=band_counts,
        tasks=items,
    )
