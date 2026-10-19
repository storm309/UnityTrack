from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import Corridor
from app.schemas.domain import CorridorDetailResponse, CorridorResponse

router = APIRouter(prefix="/api/corridors", tags=["corridors"])


@router.get("", response_model=List[CorridorResponse], summary="List all railway corridors")
def list_corridors(db: Session = Depends(get_db)) -> List[Corridor]:
    """Retrieve all available railway corridors."""
    return db.query(Corridor).all()


@router.get(
    "/{corridor_id}",
    response_model=CorridorDetailResponse,
    summary="Get corridor with ordered sections",
)
def get_corridor(corridor_id: str, db: Session = Depends(get_db)) -> Corridor:
    """Retrieve specific corridor with all ordered child sections."""
    corridor = db.query(Corridor).filter(Corridor.id == corridor_id).first()
    if not corridor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corridor '{corridor_id}' not found",
        )
    return corridor
