from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator


class PriorityWeightsInput(BaseModel):
    """Configurable weights for the multi-factor priority score calculation."""

    criticality: float = Field(
        default=0.35, ge=0.0, le=1.0, description="Weight for asset criticality"
    )
    defect_severity: float = Field(
        default=0.30, ge=0.0, le=1.0, description="Weight for defect severity"
    )
    overdue_ratio: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Weight for maintenance overdue ratio"
    )
    traffic_impact: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Weight for traffic impact factor"
    )

    @model_validator(mode="after")
    def check_weights_sum(self) -> "PriorityWeightsInput":
        total = self.criticality + self.defect_severity + self.overdue_ratio + self.traffic_impact
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Priority weights must sum to 1.0 (current sum: {total:.4f})")
        return self


class FactorContributionsSchema(BaseModel):
    """Points contribution of each factor to the total 0-100 score."""

    criticality: float = Field(description="Criticality point contribution")
    defect_severity: float = Field(description="Defect severity point contribution")
    overdue_ratio: float = Field(description="Overdue ratio point contribution")
    traffic_impact: float = Field(description="Traffic impact point contribution")


class PriorityItemResponse(BaseModel):
    """Ranked maintenance task with explainable score breakdown and priority band."""

    task_id: str = Field(description="Unique task identifier")
    title: str = Field(description="Task title")
    department: str = Field(description="Department: ENGINEERING | TRACTION | SNT")
    section_id: str = Field(description="Track section ID")
    score: float = Field(description="Computed priority score (0.0 to 100.0)")
    rank: int = Field(description="Rank position (1 = highest priority)")
    priority_band: str = Field(
        description="Priority classification band: CRITICAL | HIGH | MEDIUM | LOW"
    )
    contributions: FactorContributionsSchema = Field(
        description="Detailed point breakdown by factor"
    )
    factors_normalized: Dict[str, float] = Field(
        description="Normalized factor values (0.0 to 1.0)"
    )
    raw_factors: Dict[str, Any] = Field(description="Raw input factors before normalization")


class PriorityListResponse(BaseModel):
    """Response containing ranked tasks, summary band counts, and weights used."""

    total_tasks: int = Field(description="Total number of tasks scored")
    weights_used: PriorityWeightsInput = Field(description="Weights applied for scoring")
    band_counts: Dict[str, int] = Field(
        description="Distribution count of tasks across priority bands"
    )
    tasks: List[PriorityItemResponse] = Field(
        description="Ranked list of tasks in descending priority order"
    )
