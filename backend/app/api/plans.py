"""API endpoints for CP-SAT maintenance plan generation, retrieval, and benchmarking."""

import uuid
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import (
    BlockWindow,
    Plan,
    PlannedBlock,
    Resource,
    Section,
    Task,
    TrainSlot,
)
from app.optimizer.baseline import schedule_siloed_baseline
from app.optimizer.bundling import SectionInfo, TaskItem
from app.optimizer.priority import calculate_task_priority
from app.optimizer.scheduler import SchedulerConfig, solve_maintenance_schedule
from app.optimizer.validator import validate_schedule
from app.schemas.plan import (
    ComparisonMetricsResponse,
    PlanGenerateRequest,
    PlanListResponse,
    PlanMetricsResponse,
    PlannedBlockResponse,
    PlannedTaskResponse,
    PlanResponse,
    PlanSummaryResponse,
    ValidationSummaryResponse,
)

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _extract_task_item(t: Task, corridor_id: str) -> TaskItem:
    """Map DB Task to pure optimizer TaskItem."""
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


@router.post(
    "/generate",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate optimized maintenance schedule using CP-SAT constraint solver",
)
def generate_plan(
    payload: PlanGenerateRequest,
    db: Session = Depends(get_db),
) -> PlanResponse:
    """Generate an optimal maintenance plan with multi-department bundling and 0 train conflicts."""
    # 1. Fetch domain data from DB
    sections = db.query(Section).all()
    section_map: Dict[str, SectionInfo] = {
        s.id: SectionInfo(
            id=s.id, corridor_id=s.corridor_id, name=s.name, order_index=s.order_index
        )
        for s in sections
    }
    sec_name_map = {s.id: s.name for s in sections}

    resources = db.query(Resource).all()
    crew_capacities = {r.department: r.capacity_per_window for r in resources}
    if not crew_capacities:
        crew_capacities = {"ENGINEERING": 4, "TRACTION": 2, "SNT": 3}

    # Fetch pending tasks
    task_query = db.query(Task).filter(Task.status == "PENDING")
    db_tasks = task_query.all()
    if not db_tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending tasks found to schedule. Seed the database first.",
        )

    # Convert to TaskItems
    task_items: List[TaskItem] = []
    task_map: Dict[str, TaskItem] = {}
    for t in db_tasks:
        sec = section_map.get(t.section_id)
        c_id = sec.corridor_id if sec else "CORR-01"
        if payload.corridor_id and c_id != payload.corridor_id:
            continue
        item = _extract_task_item(t, corridor_id=c_id)
        task_items.append(item)
        task_map[item.id] = item

    # Fetch BlockWindows and TrainSlots
    windows = db.query(BlockWindow).all()
    windows_data = [
        {
            "id": w.id,
            "section_id": w.section_id,
            "start_min": w.start_min,
            "end_min": w.end_min,
            "duration_min": w.duration_min,
            "is_night_window": w.is_night_window,
        }
        for w in windows
    ]

    trains = db.query(TrainSlot).all()
    trains_data = [
        {
            "id": tr.id,
            "section_id": tr.section_id,
            "start_min": tr.start_min,
            "end_min": tr.end_min,
            "train_no": tr.train_no,
            "priority": tr.priority,
        }
        for tr in trains
    ]

    # 2. Configure and Solve with CP-SAT
    solver_cfg = SchedulerConfig(
        time_limit_seconds=payload.time_limit_seconds,
        weight_num_blocks=payload.weight_num_blocks,
        weight_disruption_minutes=payload.weight_disruption_minutes,
        weight_priority_lateness=payload.weight_priority_lateness,
        allow_adjacent_sections=payload.allow_adjacent_sections,
    )

    opt_result = solve_maintenance_schedule(
        tasks=task_items,
        block_windows=windows_data,
        crew_capacities=crew_capacities,
        section_map=section_map,
        config=solver_cfg,
    )

    if opt_result.status == "INFEASIBLE":
        diag_msg = "; ".join(opt_result.infeasible_diagnostics)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maintenance scheduling is INFEASIBLE under current constraints. Diagnostics: {diag_msg}",
        )

    # 3. Run Independent Validator on CP-SAT Output
    val_result = validate_schedule(
        blocks=opt_result.blocks,
        tasks=task_map,
        train_slots=trains_data,
        block_windows=windows_data,
        crew_capacities=crew_capacities,
        section_map=section_map,
        allow_adjacent_sections=payload.allow_adjacent_sections,
        require_all_tasks_scheduled=True,
        expected_task_ids=set(task_map.keys()),
    )

    # 4. Run Baseline Siloed Scheduler for Comparison Benchmarking
    baseline_result = schedule_siloed_baseline(
        tasks=task_items,
        block_windows=windows_data,
        crew_capacities=crew_capacities,
    )

    blk_red_count = max(0, baseline_result.total_blocks - opt_result.total_blocks)
    blk_red_pct = (
        round((blk_red_count / baseline_result.total_blocks) * 100.0, 1)
        if baseline_result.total_blocks > 0
        else 0.0
    )

    dis_savings_min = max(
        0, baseline_result.total_disruption_minutes - opt_result.total_disruption_minutes
    )
    dis_savings_pct = (
        round((dis_savings_min / baseline_result.total_disruption_minutes) * 100.0, 1)
        if baseline_result.total_disruption_minutes > 0
        else 0.0
    )

    comparison_metrics = ComparisonMetricsResponse(
        baseline_blocks=baseline_result.total_blocks,
        optimized_blocks=opt_result.total_blocks,
        block_reduction_count=blk_red_count,
        block_reduction_pct=blk_red_pct,
        baseline_disruption_min=baseline_result.total_disruption_minutes,
        optimized_disruption_min=opt_result.total_disruption_minutes,
        disruption_savings_min=dis_savings_min,
        disruption_savings_pct=dis_savings_pct,
    )

    # 5. Persist Plan & PlannedBlocks in Database
    plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
    plan_model = Plan(
        id=plan_id,
        name=payload.name or "Optimized Maintenance Plan",
        status=opt_result.status,
        scenario_params={
            "weights": {
                "num_blocks": payload.weight_num_blocks,
                "disruption_minutes": payload.weight_disruption_minutes,
                "priority_lateness": payload.weight_priority_lateness,
            },
            "allow_adjacent_sections": payload.allow_adjacent_sections,
            "metrics": {
                "total_blocks": opt_result.total_blocks,
                "total_disruption_minutes": opt_result.total_disruption_minutes,
                "cross_departmental_blocks": opt_result.cross_departmental_blocks,
                "tasks_scheduled": opt_result.tasks_scheduled,
                "solve_time_seconds": opt_result.solve_time_seconds,
            },
            "comparison": comparison_metrics.model_dump(),
            "validation": {
                "is_valid": val_result.is_valid,
                "total_violations": val_result.total_violations,
                "violations": val_result.violations,
                "checks_passed": val_result.checks_passed,
            },
        },
    )
    db.add(plan_model)
    db.commit()

    # Map assignments by block_id
    assignments_by_block: Dict[str, List[PlannedTaskResponse]] = {}
    for a in opt_result.task_assignments:
        orig_t = task_map[a.task_id]
        assignments_by_block.setdefault(a.block_id, []).append(
            PlannedTaskResponse(
                task_id=a.task_id,
                title=orig_t.title,
                department=a.department,
                section_id=a.section_id,
                start_min=a.start_min,
                duration_min=a.duration_min,
                finish_min=a.finish_min,
                is_delayed=a.is_delayed,
                delay_minutes=a.delay_minutes,
                priority_score=orig_t.priority_score,
            )
        )

    planned_block_responses: List[PlannedBlockResponse] = []
    for b in opt_result.blocks:
        pb_id = f"{plan_id}-B{b.block_id.replace('OPT-BLK-', '')}"
        db_pb = PlannedBlock(
            id=pb_id,
            plan_id=plan_id,
            section_id=b.section_id,
            start_min=b.start_min,
            end_min=b.end_min,
            task_ids=b.task_ids,
            departments=b.departments,
        )
        db.add(db_pb)

        b_tasks = assignments_by_block.get(b.block_id, [])
        planned_block_responses.append(
            PlannedBlockResponse(
                id=pb_id,
                section_id=b.section_id,
                section_name=sec_name_map.get(b.section_id, b.section_id),
                start_min=b.start_min,
                end_min=b.end_min,
                duration_min=b.duration_min,
                task_ids=b.task_ids,
                departments=b.departments,
                is_cross_departmental=len(b.departments) > 1,
                requires_power_off=b.requires_power_off,
                requires_track_block=b.requires_track_block,
                tasks=b_tasks,
            )
        )

    db.commit()

    # Refresh plan to get timestamps
    db.refresh(plan_model)

    return PlanResponse(
        id=plan_id,
        name=plan_model.name,
        status=opt_result.status,
        created_at=plan_model.created_at.isoformat() if plan_model.created_at else "",
        scenario_params=plan_model.scenario_params,
        metrics=PlanMetricsResponse(
            total_blocks=opt_result.total_blocks,
            total_disruption_minutes=opt_result.total_disruption_minutes,
            cross_departmental_blocks=opt_result.cross_departmental_blocks,
            tasks_scheduled=opt_result.tasks_scheduled,
            delayed_tasks=sum(1 for a in opt_result.task_assignments if a.is_delayed),
            solve_time_seconds=opt_result.solve_time_seconds,
            status=opt_result.status,
            objective_value=opt_result.objective_value,
        ),
        comparison=comparison_metrics,
        validation=ValidationSummaryResponse(
            is_valid=val_result.is_valid,
            total_violations=val_result.total_violations,
            violations=val_result.violations,
            checks_passed=val_result.checks_passed,
        ),
        planned_blocks=planned_block_responses,
    )


@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Get details of a generated plan by ID",
)
def get_plan(
    plan_id: str,
    db: Session = Depends(get_db),
) -> PlanResponse:
    """Retrieve full plan with blocks, validation, and metrics."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found",
        )

    sections = db.query(Section).all()
    sec_name_map = {s.id: s.name for s in sections}

    tasks = db.query(Task).all()
    task_lookup = {t.id: t for t in tasks}

    block_responses: List[PlannedBlockResponse] = []
    for pb in plan.planned_blocks:
        b_tasks: List[PlannedTaskResponse] = []
        for tid in pb.task_ids:
            t = task_lookup.get(tid)
            if t:
                b_tasks.append(
                    PlannedTaskResponse(
                        task_id=t.id,
                        title=t.title,
                        department=t.department,
                        section_id=t.section_id,
                        start_min=pb.start_min,
                        duration_min=t.duration_min,
                        finish_min=pb.start_min + t.duration_min,
                        is_delayed=(pb.start_min + t.duration_min) > t.deadline,
                        delay_minutes=max(0, (pb.start_min + t.duration_min) - t.deadline),
                        priority_score=0.0,
                    )
                )

        block_responses.append(
            PlannedBlockResponse(
                id=pb.id,
                section_id=pb.section_id,
                section_name=sec_name_map.get(pb.section_id, pb.section_id),
                start_min=pb.start_min,
                end_min=pb.end_min,
                duration_min=pb.end_min - pb.start_min,
                task_ids=pb.task_ids,
                departments=pb.departments,
                is_cross_departmental=len(pb.departments) > 1,
                requires_power_off="TRACTION" in pb.departments,
                requires_track_block=True,
                tasks=b_tasks,
            )
        )

    block_responses.sort(key=lambda b: (b.start_min, b.section_id))

    scenario_params = plan.scenario_params or {}
    metrics_dict = scenario_params.get("metrics", {})
    comp_dict = scenario_params.get("comparison")
    val_dict = scenario_params.get("validation", {})

    return PlanResponse(
        id=plan.id,
        name=plan.name,
        status=plan.status,
        created_at=plan.created_at.isoformat() if plan.created_at else "",
        scenario_params=scenario_params,
        metrics=PlanMetricsResponse(
            total_blocks=metrics_dict.get("total_blocks", len(block_responses)),
            total_disruption_minutes=metrics_dict.get(
                "total_disruption_minutes", sum(b.duration_min for b in block_responses)
            ),
            cross_departmental_blocks=metrics_dict.get(
                "cross_departmental_blocks",
                sum(1 for b in block_responses if b.is_cross_departmental),
            ),
            tasks_scheduled=metrics_dict.get(
                "tasks_scheduled", sum(len(b.tasks) for b in block_responses)
            ),
            delayed_tasks=metrics_dict.get("delayed_tasks", 0),
            solve_time_seconds=metrics_dict.get("solve_time_seconds", 0.0),
            status=plan.status,
        ),
        comparison=ComparisonMetricsResponse(**comp_dict) if comp_dict else None,
        validation=ValidationSummaryResponse(
            is_valid=val_dict.get("is_valid", True),
            total_violations=val_dict.get("total_violations", 0),
            violations=val_dict.get("violations", []),
            checks_passed=val_dict.get("checks_passed", []),
        ),
        planned_blocks=block_responses,
    )


@router.get(
    "",
    response_model=PlanListResponse,
    summary="List all generated plans",
)
def list_plans(
    db: Session = Depends(get_db),
) -> PlanListResponse:
    """Return summaries of all generated maintenance plans."""
    plans = db.query(Plan).order_by(Plan.created_at.desc()).all()
    summaries: List[PlanSummaryResponse] = []

    for p in plans:
        params = p.scenario_params or {}
        metrics = params.get("metrics", {})
        val = params.get("validation", {})

        summaries.append(
            PlanSummaryResponse(
                id=p.id,
                name=p.name,
                status=p.status,
                created_at=p.created_at.isoformat() if p.created_at else "",
                total_blocks=metrics.get("total_blocks", len(p.planned_blocks)),
                total_disruption_minutes=metrics.get("total_disruption_minutes", 0),
                tasks_scheduled=metrics.get("tasks_scheduled", 0),
                is_valid=val.get("is_valid", True),
            )
        )

    return PlanListResponse(total_plans=len(summaries), plans=summaries)
