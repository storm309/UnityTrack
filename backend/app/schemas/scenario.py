"""Pydantic schemas for Section 5 What-If Scenario Simulator."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EmergencyTaskInput(BaseModel):
    """Parameter schema for introducing an emergency or unscheduled maintenance task."""

    id: Optional[str] = Field(None, description="Optional custom ID. Auto-generated if omitted.")
    title: str = Field(..., description="Descriptive task title, e.g., 'Emergency Broken Rail Replacement'")
    department: str = Field(..., description="ENGINEERING | TRACTION | SNT")
    section_id: str = Field(..., description="Section where the emergency occurred, e.g., 'SEC-02'")
    asset_type: str = Field("General", description="Asset type (e.g., Track, OHE, Signal)")
    duration_min: int = Field(..., gt=0, le=480, description="Task duration in minutes")
    earliest_start: int = Field(0, ge=0, description="Earliest permissible start minute")
    deadline: int = Field(..., gt=0, description="Hard deadline in minutes from timeline start")
    crew_needed: int = Field(1, ge=1, le=10, description="Number of crews required")
    requires_power_off: bool = Field(False, description="Whether traction power shutdown is required")
    requires_track_block: bool = Field(True, description="Whether absolute track block is required")
    criticality: int = Field(5, ge=1, le=5, description="Criticality rating (default 5 for emergencies)")
    defect_severity: int = Field(5, ge=1, le=5, description="Defect severity (default 5 for emergencies)")
    traffic_impact: float = Field(0.8, ge=0.0, le=1.0, description="Traffic impact score")


class SectionRestrictionInput(BaseModel):
    """Parameter schema for closing or restricting track section during a time window."""

    section_id: str = Field(..., description="Target section ID, e.g., 'SEC-01'")
    start_min: int = Field(..., ge=0, description="Start minute of restriction")
    end_min: int = Field(..., gt=0, description="End minute of restriction")
    restriction_type: str = Field(
        "CLOSED", description="CLOSED (no maintenance windows allowed) | SPEED_RESTRICTED"
    )
    reason: Optional[str] = Field(
        "Emergency track maintenance / Weather alert", description="Operational justification"
    )


class TrainSlotInput(BaseModel):
    """Parameter schema for injecting a special or unscheduled train slot."""

    id: Optional[str] = Field(None, description="Train slot ID. Auto-generated if omitted.")
    section_id: str = Field(..., description="Track section traversed by train")
    train_no: str = Field(..., description="Train number, e.g., 'SPL-09901'")
    start_min: int = Field(..., ge=0, description="Arrival / entry minute into section")
    end_min: int = Field(..., gt=0, description="Departure / exit minute from section")
    priority: int = Field(1, ge=1, le=5, description="Train priority (1 highest)")


class ScenarioWeightOverrides(BaseModel):
    """Overrides for CP-SAT objective function weights."""

    weight_num_blocks: Optional[float] = Field(None, ge=0.0)
    weight_disruption_minutes: Optional[float] = Field(None, ge=0.0)
    weight_priority_lateness: Optional[float] = Field(None, ge=0.0)


class ScenarioParameters(BaseModel):
    """Overlay parameters defining a what-if scenario without mutating base data."""

    add_tasks: List[EmergencyTaskInput] = Field(default_factory=list, description="Emergency tasks to inject")
    restrict_sections: List[SectionRestrictionInput] = Field(
        default_factory=list, description="Section closure intervals"
    )
    deadline_overrides: Dict[str, int] = Field(
        default_factory=dict, description="Task ID to new deadline in minutes"
    )
    capacity_overrides: Dict[str, int] = Field(
        default_factory=dict, description="Department to crew capacity per window overrides"
    )
    weight_overrides: Optional[ScenarioWeightOverrides] = Field(
        default=None, description="Optimizer objective weight adjustments"
    )
    add_train_slots: List[TrainSlotInput] = Field(
        default_factory=list, description="Additional train slots that consume timetable gaps"
    )
    remove_train_slot_ids: List[str] = Field(
        default_factory=list, description="Train slot IDs to cancel/remove, opening timetable gaps"
    )


class ScenarioRunRequest(BaseModel):
    """Request payload to execute a what-if scenario."""

    name: str = Field(..., min_length=2, max_length=255, description="Scenario name")
    description: Optional[str] = Field(default=None, description="Scenario description or notes")
    params: ScenarioParameters = Field(..., description="Overlay parameters")
    time_limit_seconds: float = Field(default=15.0, gt=1.0, le=60.0, description="CP-SAT time limit")
    save_scenario: bool = Field(default=True, description="Whether to persist scenario in database")


class DelayedTaskSummary(BaseModel):
    """Details of a maintenance task that could not be completed prior to its deadline."""

    task_id: str
    department: str
    title: str
    priority_score: float
    deadline: int
    finish_min: int
    delay_minutes: int
    is_high_priority: bool


class ScenarioMetrics(BaseModel):
    """Comprehensive performance metrics returned for a scenario execution."""

    status: str = Field(..., description="OPTIMAL | FEASIBLE | INFEASIBLE | TIMEOUT")
    objective_value: Optional[float] = None
    solve_time_seconds: float
    total_blocks: int
    total_disruption_minutes: int
    cross_departmental_blocks: int
    tasks_scheduled: int
    total_tasks_count: int
    delayed_tasks: int
    high_priority_delays: int
    total_delay_minutes: int
    delayed_task_details: List[DelayedTaskSummary] = Field(default_factory=list)
    composite_penalty_score: float = Field(
        ..., description="Standardized multi-criteria evaluation penalty score"
    )


class ScenarioDetailResponse(BaseModel):
    """Full detail of a scenario, including metrics, blocks, and task assignments."""

    id: str
    name: str
    description: Optional[str] = None
    plan_id: Optional[str] = None
    created_at: str
    params: ScenarioParameters
    metrics: ScenarioMetrics
    blocks_count: int
    infeasible_diagnostics: Optional[List[str]] = None


class ScenarioSummaryResponse(BaseModel):
    """Summary item for scenario listing."""

    id: str
    name: str
    created_at: str
    status: str
    total_blocks: int
    total_disruption_minutes: int
    delayed_tasks: int
    high_priority_delays: int
    composite_penalty_score: float


class ScenarioCompareItem(BaseModel):
    """Scenario specification inside a multi-scenario comparison request."""

    name: str = Field(..., description="Label for this scenario candidate")
    scenario_id: Optional[str] = Field(None, description="ID of existing saved scenario, if reusing")
    params: Optional[ScenarioParameters] = Field(
        None, description="Overlay parameters (required if scenario_id is not specified)"
    )


class ScenarioCompareRequest(BaseModel):
    """Request payload to compare 2 to 4 what-if scenarios side-by-side."""

    scenarios: List[ScenarioCompareItem] = Field(
        ..., min_length=2, max_length=4, description="List of 2 to 4 scenario candidates to evaluate"
    )
    include_baseline: bool = Field(
        True, description="Whether to include unbundled siloed baseline as a reference point"
    )
    time_limit_seconds: float = Field(15.0, gt=1.0, le=60.0)


class ScenarioComparisonResultItem(BaseModel):
    """Evaluated metrics for a single scenario in a comparative analysis."""

    name: str
    scenario_id: Optional[str] = None
    status: str
    total_blocks: int
    total_disruption_minutes: int
    cross_departmental_blocks: int
    delayed_tasks: int
    high_priority_delays: int
    total_delay_minutes: int
    solve_time_seconds: float
    composite_penalty_score: float
    rank: int
    is_best: bool
    evaluation_notes: str


class ScenarioComparisonResponse(BaseModel):
    """Complete response returned by the multi-scenario comparison engine."""

    scenarios_evaluated: int
    ranking_rule: str = Field(
        ...,
        description="Explicit rule definition: Penalizes infeasibility (10000), high-priority delays (5000), total delays (1000), blocks (100), and disruption minutes (1).",
    )
    best_scenario_name: str
    best_scenario_reason: str
    comparison_table: List[ScenarioComparisonResultItem]
    delta_vs_baseline: Optional[Dict[str, Any]] = None
