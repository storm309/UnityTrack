from app.api.corridors import router as corridors_router
from app.api.health import router as health_router
from app.api.priority import router as priority_router
from app.api.resources import router as resources_router
from app.api.sections import router as sections_router
from app.api.seed import router as seed_router
from app.api.tasks import router as tasks_router
from app.api.trains import router as trains_router
from app.api.windows import router as windows_router

__all__ = [
    "health_router",
    "corridors_router",
    "sections_router",
    "tasks_router",
    "trains_router",
    "windows_router",
    "resources_router",
    "seed_router",
    "priority_router",
]
