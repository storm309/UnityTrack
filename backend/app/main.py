import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.bundles import router as bundles_router
from app.api.corridors import router as corridors_router
from app.api.health import router as health_router
from app.api.priority import router as priority_router
from app.api.resources import router as resources_router
from app.api.sections import router as sections_router
from app.api.seed import router as seed_router
from app.api.tasks import router as tasks_router
from app.api.trains import router as trains_router
from app.api.windows import router as windows_router
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("unitytrack")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info("Starting UnityTrack API (env: %s)", settings.ENVIRONMENT)
    yield
    logger.info("Stopping UnityTrack API")


def create_app() -> FastAPI:
    """Factory creating configured FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="UnityTrack API",
        description="Decision-support platform for Indian Railways maintenance planning",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(health_router)
    app.include_router(corridors_router)
    app.include_router(sections_router)
    app.include_router(tasks_router)
    app.include_router(trains_router)
    app.include_router(windows_router)
    app.include_router(resources_router)
    app.include_router(priority_router)
    app.include_router(bundles_router)
    app.include_router(seed_router)

    return app


app = create_app()
