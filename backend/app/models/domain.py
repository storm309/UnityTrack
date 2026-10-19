from datetime import datetime
from typing import Any, List

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Corridor(Base):
    """Corridor representing a major railway route with multiple ordered sections."""

    __tablename__ = "corridors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    sections: Mapped[List["Section"]] = relationship(
        "Section",
        back_populates="corridor",
        order_by="Section.order_index",
        cascade="all, delete-orphan",
    )


class Section(Base):
    """Section representing a track block between two stations on a corridor."""

    __tablename__ = "sections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    corridor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("corridors.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    km_start: Mapped[float] = mapped_column(Float, nullable=False)
    km_end: Mapped[float] = mapped_column(Float, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    corridor: Mapped["Corridor"] = relationship("Corridor", back_populates="sections")
    tasks: Mapped[List["Task"]] = relationship(
        "Task", back_populates="section", cascade="all, delete-orphan"
    )
    train_slots: Mapped[List["TrainSlot"]] = relationship(
        "TrainSlot", back_populates="section", cascade="all, delete-orphan"
    )
    block_windows: Mapped[List["BlockWindow"]] = relationship(
        "BlockWindow", back_populates="section", cascade="all, delete-orphan"
    )


class Task(Base):
    """Maintenance task raised by Engineering, Traction, or Signal & Telecom."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    department: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # ENGINEERING | TRACTION | SNT
    section_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    earliest_start: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[int] = mapped_column(Integer, nullable=False)
    criticality: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    defect_severity: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    last_done_date: Mapped[str] = mapped_column(String(32), nullable=False)
    due_date: Mapped[str] = mapped_column(String(32), nullable=False)
    traffic_impact: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    crew_needed: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_power_off: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_track_block: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False
    )  # PENDING | SCHEDULED | COMPLETED | CANCELLED

    section: Mapped["Section"] = relationship("Section", back_populates="tasks")


class TrainSlot(Base):
    """Occupied timetable window on a track section for a scheduled train."""

    __tablename__ = "train_slots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    corridor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("corridors.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    train_no: Mapped[str] = mapped_column(String(32), nullable=False)
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 (1 highest)

    section: Mapped["Section"] = relationship("Section", back_populates="train_slots")


class Resource(Base):
    """Departmental capacity limit per maintenance window."""

    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    department: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # ENGINEERING | TRACTION | SNT
    capacity_per_window: Mapped[int] = mapped_column(Integer, nullable=False)


class BlockWindow(Base):
    """Permissible maintenance window on a section derived from timetable gaps."""

    __tablename__ = "block_windows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    section_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    is_night_window: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    section: Mapped["Section"] = relationship("Section", back_populates="block_windows")


class Plan(Base):
    """Generated maintenance schedule plan."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    scenario_params: Mapped[Any] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="DRAFT", nullable=False
    )  # DRAFT | OPTIMAL | FEASIBLE | INFEASIBLE

    planned_blocks: Mapped[List["PlannedBlock"]] = relationship(
        "PlannedBlock", back_populates="plan", cascade="all, delete-orphan"
    )


class PlannedBlock(Base):
    """An allocated maintenance block in a plan, bundling multiple tasks."""

    __tablename__ = "planned_blocks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    start_min: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, nullable=False)
    task_ids: Mapped[Any] = mapped_column(JSON, nullable=False)  # List[str]
    departments: Mapped[Any] = mapped_column(JSON, nullable=False)  # List[str]

    plan: Mapped["Plan"] = relationship("Plan", back_populates="planned_blocks")


class Scenario(Base):
    """What-if scenario run with parameters and computed schedule metrics."""

    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    params: Mapped[Any] = mapped_column(JSON, nullable=False)
    metrics: Mapped[Any] = mapped_column(JSON, nullable=False)
