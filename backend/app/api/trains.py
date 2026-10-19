from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import TrainSlot
from app.schemas.domain import TrainSlotResponse

router = APIRouter(prefix="/api/trains", tags=["trains"])


@router.get("", response_model=List[TrainSlotResponse], summary="List train timetable slots")
def list_trains(
    corridor_id: Optional[str] = Query(default=None, description="Filter by corridor ID"),
    section_id: Optional[str] = Query(default=None, description="Filter by section ID"),
    train_no: Optional[str] = Query(default=None, description="Filter by train number"),
    db: Session = Depends(get_db),
) -> List[TrainSlot]:
    """Retrieve train timetable slots with optional corridor, section, and train number filtering."""
    query = db.query(TrainSlot)
    if corridor_id:
        query = query.filter(TrainSlot.corridor_id == corridor_id)
    if section_id:
        query = query.filter(TrainSlot.section_id == section_id)
    if train_no:
        query = query.filter(TrainSlot.train_no.ilike(f"%{train_no}%"))
    return query.order_by(TrainSlot.start_min).all()
