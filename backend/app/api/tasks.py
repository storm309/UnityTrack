import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import Section, Task
from app.schemas.domain import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

VALID_DEPARTMENTS = {"ENGINEERING", "TRACTION", "SNT"}
VALID_STATUSES = {"PENDING", "SCHEDULED", "COMPLETED", "CANCELLED"}


@router.get("", response_model=List[TaskResponse], summary="List maintenance tasks with filtering")
def list_tasks(
    department: Optional[str] = Query(default=None, description="Filter by department"),
    section_id: Optional[str] = Query(default=None, description="Filter by section ID"),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    db: Session = Depends(get_db),
) -> List[Task]:
    """List maintenance tasks with optional department, section, and status filters."""
    query = db.query(Task)
    if department:
        query = query.filter(Task.department == department.upper())
    if section_id:
        query = query.filter(Task.section_id == section_id)
    if status_filter:
        query = query.filter(Task.status == status_filter.upper())
    return query.order_by(Task.id).all()


@router.get("/{task_id}", response_model=TaskResponse, summary="Get maintenance task by ID")
def get_task(task_id: str, db: Session = Depends(get_db)) -> Task:
    """Retrieve details for a single maintenance task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )
    return task


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create maintenance task",
)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)) -> Task:
    """Create a new maintenance task with constraint validation."""
    # Validate department
    dept = task_in.department.upper()
    if dept not in VALID_DEPARTMENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid department '{task_in.department}'. Must be one of {sorted(VALID_DEPARTMENTS)}",
        )

    # Validate section exists
    section = db.query(Section).filter(Section.id == task_in.section_id).first()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section '{task_in.section_id}' does not exist",
        )

    # Validate deadline feasibility
    if task_in.deadline < task_in.earliest_start + task_in.duration_min:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Infeasible task constraints: deadline ({task_in.deadline}) must be >= "
                f"earliest_start ({task_in.earliest_start}) + duration ({task_in.duration_min}) "
                f"= {task_in.earliest_start + task_in.duration_min}"
            ),
        )

    task_id = task_in.id or f"TASK-{uuid.uuid4().hex[:6].upper()}"

    # Check for existing ID conflict
    if db.query(Task).filter(Task.id == task_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task with ID '{task_id}' already exists",
        )

    task_data = task_in.model_dump()
    task_data["id"] = task_id
    task_data["department"] = dept

    new_task = Task(**task_data)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task


@router.put("/{task_id}", response_model=TaskResponse, summary="Update maintenance task")
def update_task(task_id: str, task_in: TaskUpdate, db: Session = Depends(get_db)) -> Task:
    """Update existing maintenance task attributes."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )

    update_data = task_in.model_dump(exclude_unset=True)

    if "department" in update_data:
        dept = update_data["department"].upper()
        if dept not in VALID_DEPARTMENTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid department '{update_data['department']}'. Must be one of {sorted(VALID_DEPARTMENTS)}",
            )
        update_data["department"] = dept

    if "section_id" in update_data:
        sec = db.query(Section).filter(Section.id == update_data["section_id"]).first()
        if not sec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Section '{update_data['section_id']}' does not exist",
            )

    if "status" in update_data:
        st = update_data["status"].upper()
        if st not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{update_data['status']}'. Must be one of {sorted(VALID_STATUSES)}",
            )
        update_data["status"] = st

    # Check timing feasibility with new or existing values
    new_earliest = update_data.get("earliest_start", task.earliest_start)
    new_duration = update_data.get("duration_min", task.duration_min)
    new_deadline = update_data.get("deadline", task.deadline)

    if new_deadline < new_earliest + new_duration:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Infeasible task constraints: deadline ({new_deadline}) must be >= "
                f"earliest_start ({new_earliest}) + duration ({new_duration}) "
                f"= {new_earliest + new_duration}"
            ),
        )

    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete(
    "/{task_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete maintenance task"
)
def delete_task(task_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a maintenance task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )
    db.delete(task)
    db.commit()
