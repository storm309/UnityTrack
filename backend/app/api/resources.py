from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.domain import Resource
from app.schemas.domain import ResourceResponse

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("", response_model=List[ResourceResponse], summary="List departmental maintenance resources")
def list_resources(
    department: Optional[str] = Query(default=None, description="Filter by department"),
    db: Session = Depends(get_db),
) -> List[Resource]:
    """Retrieve departmental maintenance capacity limits."""
    query = db.query(Resource)
    if department:
        query = query.filter(Resource.department == department.upper())
    return query.order_by(Resource.department).all()
