from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import BlockWindow
from app.schemas.domain import BlockWindowResponse

router = APIRouter(prefix="/api/windows", tags=["windows"])


@router.get(
    "", response_model=List[BlockWindowResponse], summary="List allowable maintenance block windows"
)
def list_windows(
    section_id: Optional[str] = Query(default=None, description="Filter by section ID"),
    is_night_window: Optional[bool] = Query(
        default=None, description="Filter by night window flag"
    ),
    db: Session = Depends(get_db),
) -> List[BlockWindow]:
    """Retrieve permissible maintenance windows derived from timetable gaps."""
    query = db.query(BlockWindow)
    if section_id:
        query = query.filter(BlockWindow.section_id == section_id)
    if is_night_window is not None:
        query = query.filter(BlockWindow.is_night_window == is_night_window)
    return query.order_by(BlockWindow.start_min).all()
