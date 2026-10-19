from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.domain import SeedRequest, SeedResponse
from app.seed import seed_database

router = APIRouter(prefix="/api/seed", tags=["seed"])


@router.post(
    "",
    response_model=SeedResponse,
    status_code=status.HTTP_200_OK,
    summary="Seed database with deterministic synthetic data",
)
def trigger_seed(
    request: SeedRequest = SeedRequest(),
    db: Session = Depends(get_db),
) -> SeedResponse:
    """Seed or re-seed the database with deterministic synthetic railway data."""
    summary = seed_database(db, seed=request.seed, reset=request.reset)
    return SeedResponse(status="ok", seed=request.seed, records=summary)
