import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.health import HealthResponse

logger = logging.getLogger("unitytrack.health")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service health status")
def get_health(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> HealthResponse:
    """Return the health status of UnityTrack API service and database connectivity."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database health check failed: %s", exc)
        db_status = "degraded"

    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version="0.1.0",
        database=db_status,
    )
