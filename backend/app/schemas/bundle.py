"""Pydantic schemas for multi-department maintenance task bundling and compatibility API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TaskSummarySchema(BaseModel):
    """Brief task preview within a bundle candidate."""

    id: str
    title: str
    department: str
    asset_type: str
    duration_min: int
    priority_score: float


class BundleCandidateSchema(BaseModel):
    """Candidate bundle of mutually compatible tasks sharing a maintenance block."""

    bundle_id: str = Field(description="Deterministic bundle identifier")
    task_ids: List[str] = Field(description="List of task IDs bundled together")
    section_id: str = Field(description="Physical track section ID")
    corridor_id: str = Field(description="Corridor ID")
    departments: List[str] = Field(description="List of departments involved")
    is_cross_departmental: bool = Field(description="True if bundling across multiple departments")
    execution_mode: str = Field(description="Execution mode: PARALLEL | SEQUENTIAL | HYBRID")
    duration_min: int = Field(description="Total required block duration in minutes")
    disruption_savings_min: int = Field(
        description="Minutes saved compared to separate unbundled blocks"
    )
    efficiency_gain_pct: float = Field(
        description="Percentage reduction in corridor disruption time"
    )
    earliest_start: int = Field(description="Feasible bundle earliest start (minute offset)")
    deadline: int = Field(description="Feasible bundle deadline (minute offset)")
    feasibility_window_min: int = Field(
        description="Available window length (deadline - earliest_start)"
    )
    requires_power_off: bool = Field(
        description="True if OHE 25kV de-energization power block is required"
    )
    requires_track_block: bool = Field(description="True if track possession block is required")
    crew_needed_by_dept: Dict[str, int] = Field(
        description="Concurrent crew required broken down by department"
    )
    combined_priority_score: float = Field(
        description="Aggregate priority score for all tasks in bundle"
    )
    compatibility_reasons: List[str] = Field(
        description="Explainable reasons why tasks are compatible"
    )
    tasks_summary: List[TaskSummarySchema] = Field(description="Task details in this bundle")


class CandidateBundlesListResponse(BaseModel):
    """Response containing all discovered candidate bundles matching query filters."""

    total_candidates: int = Field(description="Total candidate bundles discovered")
    cross_departmental_count: int = Field(description="Number of multi-department bundles")
    total_potential_savings_min: int = Field(
        description="Total corridor disruption minutes saved if all best bundles executed"
    )
    candidates: List[BundleCandidateSchema] = Field(
        description="List of candidate bundles sorted by disruption savings"
    )


class PairwiseCompatibilityResponse(BaseModel):
    """Detailed response for pairwise task compatibility evaluation."""

    task_a_id: str
    task_b_id: str
    is_compatible: bool
    conflict_code: Optional[str] = None
    conflict_reason: Optional[str] = None
    execution_mode: str
    combined_duration_min: int
    disruption_savings_min: int
    requires_power_off: bool
    requires_track_block: bool
    reasons: List[str]
