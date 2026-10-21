"""Pydantic schemas for CP-SAT maintenance schedule plans, blocks, and benchmark metrics."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlanGenerateRequest(BaseModel):
    """Request payload for generating an optimized maintenance schedule."""

    name: Optional[str] = Field(
        default="Optimized Maintenance Plan", description="Human-readable plan name"
    )
    corridor_id: Optional[str] = Field(default=None, description="Optional corridor filter")
    time_limit_seconds: float = Field(
        default=30.0, ge=1.0, le=300.0, description="CP-SAT solver timeout limit in seconds"
    )
    weight_num_blocks: float = Field(
        default=1000.0, ge=0.0, description="Objective weight penalizing block openings"
    )
    weight_disruption_minutes: float = Field(
        default=5.0, ge=0.0, description="Objective weight penalizing corridor disruption duration"
    )
    weight_priority_lateness: float = Field(
        default=1.0, ge=0.0, description="Objective weight scheduling high-priority tasks earlier"
    )
    allow_adjacent_sections: bool = Field(
        default=False, description="Allow bundling across adjacent physical sections"
    )


class PlannedTaskResponse(BaseModel):
    """Scheduled task details within a planned maintenance block."""

    task_id: str
    title: str
    department: str
    section_id: str
    start_min: int
    duration_min: int
    finish_min: int
    is_delayed: bool
    delay_minutes: int
    priority_score: float


class PlannedBlockResponse(BaseModel):
    """Allocated maintenance block bundling one or more compatible tasks."""

    id: str
    section_id: str
    section_name: str
    start_min: int
    end_min: int
    duration_min: int
    task_ids: List[str]
    departments: List[str]
    is_cross_departmental: bool
    requires_power_off: bool
    requires_track_block: bool
    tasks: List[PlannedTaskResponse]


class ValidationSummaryResponse(BaseModel):
    """Independent validator results verifying all hard railway constraints."""

    is_valid: bool
    total_violations: int
    violations: List[str]
    checks_passed: List[str]


class PlanMetricsResponse(BaseModel):
    """Core optimization schedule metrics."""

    total_blocks: int
    total_disruption_minutes: int
    cross_departmental_blocks: int
    tasks_scheduled: int
    delayed_tasks: int
    solve_time_seconds: float
    status: str
    objective_value: Optional[float] = None


class ComparisonMetricsResponse(BaseModel):
    """Comparison benchmarks against the siloed departmental baseline."""

    baseline_blocks: int
    optimized_blocks: int
    block_reduction_count: int
    block_reduction_pct: float
    baseline_disruption_min: int
    optimized_disruption_min: int
    disruption_savings_min: int
    disruption_savings_pct: float


class PlanResponse(BaseModel):
    """Full maintenance schedule plan response with blocks, validation, and benchmarks."""

    id: str
    name: str
    status: str
    created_at: str
    scenario_params: Optional[Dict[str, Any]] = None
    metrics: PlanMetricsResponse
    comparison: Optional[ComparisonMetricsResponse] = None
    validation: ValidationSummaryResponse
    planned_blocks: List[PlannedBlockResponse]


class PlanSummaryResponse(BaseModel):
    """Brief summary of a generated plan."""

    id: str
    name: str
    status: str
    created_at: str
    total_blocks: int
    total_disruption_minutes: int
    tasks_scheduled: int
    is_valid: bool


class PlanListResponse(BaseModel):
    """List of generated maintenance plans."""

    total_plans: int
    plans: List[PlanSummaryResponse]
