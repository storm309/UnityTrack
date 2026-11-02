"""API endpoints for Section 5 What-If Scenario Simulator and Comparison Engine."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import (
    BlockWindow,
    Plan,
    PlannedBlock,
    Resource,
    Scenario,
    Section,
    Task,
    TrainSlot,
)
from app.optimizer.bundling import SectionInfo, TaskItem
from app.optimizer.priority import calculate_task_priority
from app.optimizer.scenario import (
    ScenarioOverlayData,
    ScenarioSimulationResult,
    compare_scenario_simulations,
    run_scenario_simulation,
)
from app.schemas.scenario import (
    DelayedTaskSummary,
    EmergencyTaskInput,
    ScenarioCompareRequest,
    ScenarioComparisonResponse,
    ScenarioComparisonResultItem,
    ScenarioDetailResponse,
    ScenarioMetrics,
    ScenarioParameters,
    ScenarioRunRequest,
    ScenarioSummaryResponse,
)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _extract_task_item(t: Task, corridor_id: str) -> TaskItem:
    """Map DB Task model to pure optimizer TaskItem."""
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


def _convert_emergency_task(emg: EmergencyTaskInput, idx: int, corridor_id: str = "CORR-01") -> TaskItem:
    """Convert an EmergencyTaskInput schema to a full optimizer TaskItem."""
    task_id = emg.id if emg.id else f"EMG-TASK-{idx:03d}"
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    priority_res = calculate_task_priority(
        {
            "id": task_id,
            "criticality": emg.criticality,
            "defect_severity": emg.defect_severity,
            "due_date": today_str,
            "last_done_date": today_str,
            "traffic_impact": emg.traffic_impact,
        }
    )
    return TaskItem(
        id=task_id,
        title=emg.title,
        department=emg.department.upper(),
        section_id=emg.section_id,
        corridor_id=corridor_id,
        asset_type=emg.asset_type,
        duration_min=emg.duration_min,
        earliest_start=emg.earliest_start,
        deadline=emg.deadline,
        crew_needed=emg.crew_needed,
        requires_power_off=emg.requires_power_off,
        requires_track_block=emg.requires_track_block,
        criticality=emg.criticality,
        defect_severity=emg.defect_severity,
        priority_score=priority_res.score,
    )


def _load_base_railway_data(
    db: Session,
) -> tuple[
    List[TaskItem],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    Dict[str, int],
    Dict[str, SectionInfo],
]:
    """Load canonical domain entities from DB without applying any mutations."""
    sections = db.query(Section).all()
    section_map: Dict[str, SectionInfo] = {
        s.id: SectionInfo(
            id=s.id, corridor_id=s.corridor_id, name=s.name, order_index=s.order_index
        )
        for s in sections
    }

    resources = db.query(Resource).all()
    crew_capacities = {r.department: r.capacity_per_window for r in resources}
    if not crew_capacities:
        crew_capacities = {"ENGINEERING": 4, "TRACTION": 2, "SNT": 3}

    tasks = db.query(Task).filter(Task.status == "PENDING").all()
    task_items: List[TaskItem] = []
    for t in tasks:
        sec = section_map.get(t.section_id)
        c_id = sec.corridor_id if sec else "CORR-01"
        task_items.append(_extract_task_item(t, corridor_id=c_id))

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

    return task_items, windows_data, trains_data, crew_capacities, section_map


def _build_overlay_data(
    name: str,
    params: ScenarioParameters,
    section_map: Dict[str, SectionInfo],
) -> ScenarioOverlayData:
    """Translate Pydantic ScenarioParameters into pure ScenarioOverlayData."""
    add_tasks: List[TaskItem] = []
    for idx, emg in enumerate(params.add_tasks, start=1):
        sec = section_map.get(emg.section_id)
        c_id = sec.corridor_id if sec else "CORR-01"
        add_tasks.append(_convert_emergency_task(emg, idx=idx, corridor_id=c_id))

    restrictions = [
        {
            "section_id": r.section_id,
            "start_min": r.start_min,
            "end_min": r.end_min,
            "restriction_type": r.restriction_type,
            "reason": r.reason,
        }
        for r in params.restrict_sections
    ]

    added_trains = [
        {
            "id": ts.id if ts.id else f"EXTRA-TRN-{idx:03d}",
            "section_id": ts.section_id,
            "train_no": ts.train_no,
            "start_min": ts.start_min,
            "end_min": ts.end_min,
            "priority": ts.priority,
        }
        for idx, ts in enumerate(params.add_train_slots, start=1)
    ]

    weights: Dict[str, float] = {}
    if params.weight_overrides:
        if params.weight_overrides.weight_num_blocks is not None:
            weights["weight_num_blocks"] = params.weight_overrides.weight_num_blocks
        if params.weight_overrides.weight_disruption_minutes is not None:
            weights["weight_disruption_minutes"] = params.weight_overrides.weight_disruption_minutes
        if params.weight_overrides.weight_priority_lateness is not None:
            weights["weight_priority_lateness"] = params.weight_overrides.weight_priority_lateness

    return ScenarioOverlayData(
        name=name,
        add_tasks=add_tasks,
        restrict_sections=restrictions,
        deadline_overrides=dict(params.deadline_overrides),
        capacity_overrides=dict(params.capacity_overrides),
        weight_overrides=weights,
        add_train_slots=added_trains,
        remove_train_slot_ids=list(params.remove_train_slot_ids),
    )


@router.post(
    "/run",
    response_model=ScenarioDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a what-if scenario on top of base data without mutating it",
)
def run_scenario(
    payload: ScenarioRunRequest,
    db: Session = Depends(get_db),
) -> ScenarioDetailResponse:
    """Execute what-if scenario with overlays (tasks, closures, capacity, deadlines, train slots)."""
    (
        base_tasks,
        base_windows,
        base_trains,
        base_capacities,
        section_map,
    ) = _load_base_railway_data(db)

    overlay = _build_overlay_data(
        name=payload.name,
        params=payload.params,
        section_map=section_map,
    )

    result = run_scenario_simulation(
        base_tasks=base_tasks,
        base_windows=base_windows,
        base_train_slots=base_trains,
        base_capacities=base_capacities,
        overlay=overlay,
        time_limit_seconds=payload.time_limit_seconds,
    )

    scenario_id = f"SCEN-{uuid.uuid4().hex[:8].upper()}"
    plan_id: Optional[str] = None

    # Optionally persist in database
    if payload.save_scenario:
        if result.status in ("OPTIMAL", "FEASIBLE"):
            plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
            db_plan = Plan(
                id=plan_id,
                name=f"Plan for Scenario: {payload.name}",
                scenario_params=payload.params.model_dump(),
                status=result.status,
            )
            db.add(db_plan)

            for b in result.blocks:
                p_block = PlannedBlock(
                    id=f"{plan_id}-{b.block_id}",
                    plan_id=plan_id,
                    section_id=b.section_id,
                    start_min=b.start_min,
                    end_min=b.end_min,
                    task_ids=b.task_ids,
                    departments=b.departments,
                )
                db.add(p_block)

        # Build metrics dict for DB
        metrics_dict = {
            "status": result.status,
            "objective_value": result.objective_value,
            "solve_time_seconds": result.solve_time_seconds,
            "total_blocks": result.total_blocks,
            "total_disruption_minutes": result.total_disruption_minutes,
            "cross_departmental_blocks": result.cross_departmental_blocks,
            "tasks_scheduled": result.tasks_scheduled,
            "total_tasks_count": result.total_tasks_count,
            "delayed_tasks": result.delayed_tasks,
            "high_priority_delays": result.high_priority_delays,
            "total_delay_minutes": result.total_delay_minutes,
            "composite_penalty_score": result.composite_penalty_score,
            "delayed_task_details": [
                {
                    "task_id": d.task_id,
                    "department": d.department,
                    "title": d.title,
                    "priority_score": d.priority_score,
                    "deadline": d.deadline,
                    "finish_min": d.finish_min,
                    "delay_minutes": d.delay_minutes,
                    "is_high_priority": d.is_high_priority,
                }
                for d in result.delayed_task_details
            ],
            "blocks_count": len(result.blocks),
        }

        db_scen = Scenario(
            id=scenario_id,
            plan_id=plan_id,
            name=payload.name,
            description=payload.description,
            params=payload.params.model_dump(),
            metrics=metrics_dict,
        )
        db.add(db_scen)
        db.commit()

    created_iso = datetime.now(timezone.utc).isoformat()

    metrics_resp = ScenarioMetrics(
        status=result.status,
        objective_value=result.objective_value,
        solve_time_seconds=result.solve_time_seconds,
        total_blocks=result.total_blocks,
        total_disruption_minutes=result.total_disruption_minutes,
        cross_departmental_blocks=result.cross_departmental_blocks,
        tasks_scheduled=result.tasks_scheduled,
        total_tasks_count=result.total_tasks_count,
        delayed_tasks=result.delayed_tasks,
        high_priority_delays=result.high_priority_delays,
        total_delay_minutes=result.total_delay_minutes,
        delayed_task_details=[
            DelayedTaskSummary(
                task_id=d.task_id,
                department=d.department,
                title=d.title,
                priority_score=d.priority_score,
                deadline=d.deadline,
                finish_min=d.finish_min,
                delay_minutes=d.delay_minutes,
                is_high_priority=d.is_high_priority,
            )
            for d in result.delayed_task_details
        ],
        composite_penalty_score=result.composite_penalty_score,
    )

    return ScenarioDetailResponse(
        id=scenario_id,
        name=payload.name,
        description=payload.description,
        plan_id=plan_id,
        created_at=created_iso,
        params=payload.params,
        metrics=metrics_resp,
        blocks_count=len(result.blocks),
        infeasible_diagnostics=result.infeasible_diagnostics,
    )


@router.post(
    "/compare",
    response_model=ScenarioComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare 2 to 4 what-if scenarios side-by-side with objective ranking",
)
def compare_scenarios(
    payload: ScenarioCompareRequest,
    db: Session = Depends(get_db),
) -> ScenarioComparisonResponse:
    """Evaluate 2-4 scenarios side-by-side, score them, and designate the best recommendation."""
    (
        base_tasks,
        base_windows,
        base_trains,
        base_capacities,
        section_map,
    ) = _load_base_railway_data(db)

    # Compute baseline reference if requested
    baseline_result: Optional[ScenarioSimulationResult] = None
    if payload.include_baseline:
        base_overlay = ScenarioOverlayData(name="Standard Base (No Overlays)")
        baseline_result = run_scenario_simulation(
            base_tasks=base_tasks,
            base_windows=base_windows,
            base_train_slots=base_trains,
            base_capacities=base_capacities,
            overlay=base_overlay,
            time_limit_seconds=payload.time_limit_seconds,
        )

    simulated_results: List[ScenarioSimulationResult] = []

    for item in payload.scenarios:
        # If scenario_id is provided, check if existing scenario is saved in DB
        params = item.params
        if item.scenario_id and not params:
            saved_scen = db.query(Scenario).filter(Scenario.id == item.scenario_id).first()
            if saved_scen:
                params = ScenarioParameters(**saved_scen.params)

        if not params:
            params = ScenarioParameters()

        overlay = _build_overlay_data(
            name=item.name,
            params=params,
            section_map=section_map,
        )

        sim_res = run_scenario_simulation(
            base_tasks=base_tasks,
            base_windows=base_windows,
            base_train_slots=base_trains,
            base_capacities=base_capacities,
            overlay=overlay,
            time_limit_seconds=payload.time_limit_seconds,
        )
        simulated_results.append(sim_res)

    comparison = compare_scenario_simulations(
        scenarios=simulated_results,
        reference_result=baseline_result,
    )

    table_items: List[ScenarioComparisonResultItem] = [
        ScenarioComparisonResultItem(
            name=r.name,
            scenario_id=None,
            status=r.status,
            total_blocks=r.total_blocks,
            total_disruption_minutes=r.total_disruption_minutes,
            cross_departmental_blocks=r.cross_departmental_blocks,
            delayed_tasks=r.delayed_tasks,
            high_priority_delays=r.high_priority_delays,
            total_delay_minutes=r.total_delay_minutes,
            solve_time_seconds=r.solve_time_seconds,
            composite_penalty_score=r.composite_penalty_score,
            rank=r.rank,
            is_best=r.is_best,
            evaluation_notes=r.evaluation_notes,
        )
        for r in comparison.ranked_scenarios
    ]

    return ScenarioComparisonResponse(
        scenarios_evaluated=comparison.scenarios_evaluated,
        ranking_rule=comparison.ranking_rule,
        best_scenario_name=comparison.best_scenario_name,
        best_scenario_reason=comparison.best_scenario_reason,
        comparison_table=table_items,
        delta_vs_baseline=comparison.delta_vs_reference,
    )


@router.get(
    "",
    response_model=List[ScenarioSummaryResponse],
    summary="List all persisted what-if scenarios",
)
def list_scenarios(
    db: Session = Depends(get_db),
) -> List[ScenarioSummaryResponse]:
    """Retrieve all previously executed and saved scenarios."""
    scenarios = db.query(Scenario).order_by(Scenario.created_at.desc()).all()
    summaries: List[ScenarioSummaryResponse] = []

    for s in scenarios:
        m = s.metrics if isinstance(s.metrics, dict) else {}
        created_str = (
            s.created_at.isoformat() if s.created_at else datetime.now(timezone.utc).isoformat()
        )
        summaries.append(
            ScenarioSummaryResponse(
                id=s.id,
                name=s.name,
                created_at=created_str,
                status=m.get("status", "UNKNOWN"),
                total_blocks=m.get("total_blocks", 0),
                total_disruption_minutes=m.get("total_disruption_minutes", 0),
                delayed_tasks=m.get("delayed_tasks", 0),
                high_priority_delays=m.get("high_priority_delays", 0),
                composite_penalty_score=m.get("composite_penalty_score", 0.0),
            )
        )

    return summaries


@router.get(
    "/{scenario_id}",
    response_model=ScenarioDetailResponse,
    summary="Retrieve details and metrics of a specific what-if scenario",
)
def get_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> ScenarioDetailResponse:
    """Get full details of a saved scenario by ID."""
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario with ID '{scenario_id}' not found",
        )

    m = s.metrics if isinstance(s.metrics, dict) else {}
    params_data = s.params if isinstance(s.params, dict) else {}
    params_obj = ScenarioParameters(**params_data)

    delays = [
        DelayedTaskSummary(**d) for d in m.get("delayed_task_details", [])
    ]

    metrics_resp = ScenarioMetrics(
        status=m.get("status", "UNKNOWN"),
        objective_value=m.get("objective_value"),
        solve_time_seconds=m.get("solve_time_seconds", 0.0),
        total_blocks=m.get("total_blocks", 0),
        total_disruption_minutes=m.get("total_disruption_minutes", 0),
        cross_departmental_blocks=m.get("cross_departmental_blocks", 0),
        tasks_scheduled=m.get("tasks_scheduled", 0),
        total_tasks_count=m.get("total_tasks_count", 0),
        delayed_tasks=m.get("delayed_tasks", 0),
        high_priority_delays=m.get("high_priority_delays", 0),
        total_delay_minutes=m.get("total_delay_minutes", 0),
        delayed_task_details=delays,
        composite_penalty_score=m.get("composite_penalty_score", 0.0),
    )

    created_str = (
        s.created_at.isoformat() if s.created_at else datetime.now(timezone.utc).isoformat()
    )

    return ScenarioDetailResponse(
        id=s.id,
        name=s.name,
        description=s.description,
        plan_id=s.plan_id,
        created_at=created_str,
        params=params_obj,
        metrics=metrics_resp,
        blocks_count=m.get("blocks_count", 0),
        infeasible_diagnostics=m.get("infeasible_diagnostics"),
    )


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved what-if scenario",
)
def delete_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete a saved scenario and any associated plan."""
    s = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario with ID '{scenario_id}' not found",
        )

    if s.plan_id:
        db.query(Plan).filter(Plan.id == s.plan_id).delete()

    db.delete(s)
    db.commit()
