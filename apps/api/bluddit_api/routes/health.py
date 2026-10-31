"""Public process health and database readiness routes."""

from fastapi import APIRouter, Request, Response
import psycopg
from psycopg_pool import PoolTimeout

from bluddit_api.routes.responses import HealthResponse
from bluddit_api.migrate import MigrationError
from bluddit_api.utils.dependencies import HealthRepositoryDep

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", responses={503: {"model": HealthResponse}})
async def ready(
    request: Request,
    response: Response,
    repository: HealthRepositoryDep,
) -> HealthResponse:
    if repository is not None:
        try:
            if await repository.is_ready(request.app.state.migrations):
                return HealthResponse(status="ok")
        except (psycopg.Error, PoolTimeout, MigrationError):
            pass
    response.status_code = 503
    return HealthResponse(status="unavailable")
