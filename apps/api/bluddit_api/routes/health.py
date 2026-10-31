"""Public process health and database readiness routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
import psycopg
from psycopg_pool import PoolTimeout

from bluddit_api.migrate import MigrationError
from bluddit_api.repositories.health import HealthRepository
from bluddit_api.utils.dependencies import get_health_repository

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    request: Request,
    repository: HealthRepository | None = Depends(get_health_repository),
):
    if repository is not None:
        try:
            if await repository.is_ready(request.app.state.migrations):
                return {"status": "ok"}
        except (psycopg.Error, PoolTimeout, MigrationError):
            pass
    return JSONResponse(status_code=503, content={"status": "unavailable"})
