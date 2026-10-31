"""Repository providers for request dependency injection."""

from fastapi import Depends

from bluddit_api.database import Database, get_database, get_optional_database
from bluddit_api.repositories.auth import AuthRepository
from bluddit_api.repositories.health import HealthRepository


async def get_auth_repository(
    database: Database = Depends(get_database),
) -> AuthRepository:
    return AuthRepository(database)


async def get_health_repository(
    database: Database | None = Depends(get_optional_database),
) -> HealthRepository | None:
    return HealthRepository(database) if database is not None else None
