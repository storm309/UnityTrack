from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ------------------ Corridor ------------------
class CorridorBase(BaseModel):
    id: str = Field(description="Unique corridor identifier")
    name: str = Field(description="Corridor name")


class SectionBase(BaseModel):
    id: str = Field(description="Unique section identifier")
    corridor_id: str = Field(description="Corridor identifier")
    name: str = Field(description="Section name")
    km_start: float = Field(description="Starting kilometer post")
    km_end: float = Field(description="Ending kilometer post")
    order_index: int = Field(description="Sequential order of the section on the corridor")

    model_config = ConfigDict(from_attributes=True)


class CorridorResponse(CorridorBase):
    model_config = ConfigDict(from_attributes=True)


class CorridorDetailResponse(CorridorBase):
    sections: List[SectionBase] = []

    model_config = ConfigDict(from_attributes=True)


# ------------------ Section ------------------
class SectionResponse(SectionBase):
    pass


# ------------------ Task ------------------
class TaskBase(BaseModel):
    department: str = Field(description="Department: ENGINEERING | TRACTION | SNT")
    section_id: str = Field(description="Section ID where task is located")
    title: str = Field(description="Task title/description")
    asset_type: str = Field(description="Asset type (Rails, OHE, Turnout, etc.)")
    duration_min: int = Field(gt=0, description="Duration in minutes")
    earliest_start: int = Field(
        ge=0, description="Earliest feasible start minute from horizon start"
    )
    deadline: int = Field(gt=0, description="Hard deadline minute from horizon start")
    criticality: int = Field(ge=1, le=5, description="Asset criticality (1 to 5)")
    defect_severity: int = Field(ge=1, le=5, description="Defect severity (1 to 5)")
    last_done_date: str = Field(description="ISO date string of last maintenance")
    due_date: str = Field(description="ISO date string when maintenance is due")
    traffic_impact: float = Field(
        ge=0.0, le=1.0, description="Normalized traffic impact factor (0.0 to 1.0)"
    )
    crew_needed: int = Field(gt=0, description="Number of crews required")
    requires_power_off: bool = Field(
        default=False, description="Whether OHE power must be turned off"
    )
    requires_track_block: bool = Field(
        default=True, description="Whether track line block is required"
    )
    status: str = Field(
        default="PENDING", description="Task status (PENDING, SCHEDULED, COMPLETED, CANCELLED)"
    )


class TaskCreate(TaskBase):
    id: Optional[str] = Field(
        default=None, description="Optional custom ID; auto-generated if omitted"
    )


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    section_id: Optional[str] = None
    asset_type: Optional[str] = None
    duration_min: Optional[int] = Field(default=None, gt=0)
    earliest_start: Optional[int] = Field(default=None, ge=0)
    deadline: Optional[int] = Field(default=None, gt=0)
    criticality: Optional[int] = Field(default=None, ge=1, le=5)
    defect_severity: Optional[int] = Field(default=None, ge=1, le=5)
    last_done_date: Optional[str] = None
    due_date: Optional[str] = None
    traffic_impact: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    crew_needed: Optional[int] = Field(default=None, gt=0)
    requires_power_off: Optional[bool] = None
    requires_track_block: Optional[bool] = None
    status: Optional[str] = None


class TaskResponse(TaskBase):
    id: str = Field(description="Unique task ID")

    model_config = ConfigDict(from_attributes=True)


# ------------------ TrainSlot ------------------
class TrainSlotResponse(BaseModel):
    id: str = Field(description="Unique train slot ID")
    corridor_id: str = Field(description="Corridor ID")
    section_id: str = Field(description="Section ID")
    train_no: str = Field(description="Train identifier")
    start_min: int = Field(description="Occupancy start minute from horizon start")
    end_min: int = Field(description="Occupancy end minute from horizon start")
    priority: int = Field(description="Train priority (1 highest to 5 lowest)")

    model_config = ConfigDict(from_attributes=True)


# ------------------ BlockWindow ------------------
class BlockWindowResponse(BaseModel):
    id: str = Field(description="Unique maintenance window ID")
    section_id: str = Field(description="Section ID")
    start_min: int = Field(description="Window start minute from horizon start")
    end_min: int = Field(description="Window end minute from horizon start")
    duration_min: int = Field(description="Duration in minutes")
    is_night_window: bool = Field(description="True if window occurs during night traffic lull")

    model_config = ConfigDict(from_attributes=True)


# ------------------ Resource ------------------
class ResourceResponse(BaseModel):
    id: str = Field(description="Resource ID")
    department: str = Field(description="Department name")
    capacity_per_window: int = Field(description="Maximum concurrent crews per window")

    model_config = ConfigDict(from_attributes=True)


# ------------------ Seed ------------------
class SeedRequest(BaseModel):
    seed: int = Field(default=42, description="Random seed for deterministic generation")
    reset: bool = Field(default=True, description="Clear existing data before seeding")


class SeedResponse(BaseModel):
    status: str = Field(default="ok")
    seed: int
    records: dict[str, int]
