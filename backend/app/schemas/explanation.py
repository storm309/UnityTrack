"""Pydantic schemas for Section 6 Explanation Generator."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class FactorExplanation(BaseModel):
    """Detailed attribution for a single priority scoring factor."""

    factor_name: str = Field(..., description="Factor identifier: criticality | severity | overdue | traffic")
    display_name: str = Field(..., description="Human-readable factor title")
    weight_pct: float = Field(..., description="Configured weight percentage (e.g., 35.0%)")
    raw_value: float = Field(..., description="Raw domain input value")
    normalized_value: float = Field(..., description="Normalized factor value between 0.0 and 1.0")
    points_contributed: float = Field(..., description="Absolute points contributed to priority score (0-100)")
    explanation: str = Field(..., description="Plain-language description of factor impact")


class PriorityExplanation(BaseModel):
    """Explainable justification for a maintenance task's priority ranking and band."""

    task_id: str
    title: str
    department: str
    priority_score: float
    priority_band: str
    criticality: int
    defect_severity: int
    due_date: str
    traffic_impact: float
    top_contributing_factors: List[FactorExplanation]
    summary: str


class BundleExplanation(BaseModel):
    """Justification for combining multiple tasks into a shared maintenance block."""

    block_id: str
    section_id: str
    section_name: str
    start_min: int
    end_min: int
    duration_min: int
    time_window_str: str
    departments: List[str]
    is_cross_departmental: bool
    task_ids: List[str]
    task_count: int
    sum_individual_durations: int
    disruption_savings_min: int
    power_off_required: bool
    track_block_required: bool
    justification: str
    safety_compatibility_notes: str


class DelayExplanation(BaseModel):
    """Root-cause explanation for why a task could not be scheduled before its deadline."""

    task_id: str
    title: str
    department: str
    section_id: str
    deadline: int
    scheduled_finish: int
    delay_minutes: int
    binding_constraint: str
    root_cause_analysis: str


class PlanRecommendationExplanation(BaseModel):
    """Comprehensive justification of why the optimized plan is superior to siloed alternatives."""

    headline: str
    summary: str
    baseline_blocks: int
    optimized_blocks: int
    blocks_saved: int
    block_reduction_pct: float
    baseline_disruption_min: int
    optimized_disruption_min: int
    disruption_savings_min: int
    disruption_savings_pct: float
    cross_departmental_blocks: int
    delayed_tasks_count: int
    key_tradeoffs: List[str]
    detailed_bullets: List[str]


class PlanExplanationsResponse(BaseModel):
    """Complete explainability payload for a generated maintenance schedule plan."""

    plan_id: str
    plan_name: str
    created_at: str
    is_llm_polished: bool = False
    recommendation: PlanRecommendationExplanation
    bundle_explanations: List[BundleExplanation]
    priority_explanations: List[PriorityExplanation]
    delay_explanations: List[DelayExplanation]
    numerical_facts: Dict[str, Any]
