from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import Section
from app.schemas.domain import SectionResponse

router = APIRouter(prefix="/api/sections", tags=["sections"])


@router.get("", response_model=List[SectionResponse], summary="List railway track sections")
def list_sections(
    corridor_id: Optional[str] = Query(default=None, description="Filter by corridor ID"),
    db: Session = Depends(get_db),
) -> List[Section]:
    """Retrieve track sections, optionally filtered by corridor."""
    query = db.query(Section)
    if corridor_id:
        query = query.filter(Section.corridor_id == corridor_id)
    return query.order_by(Section.order_index).all()


@router.get("/{section_id}", response_model=SectionResponse, summary="Get section details")
def get_section(section_id: str, db: Session = Depends(get_db)) -> Section:
    """Retrieve details of a specific track section."""
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section '{section_id}' not found",
        )
    return section
