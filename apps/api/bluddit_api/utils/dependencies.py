"""Repository providers for request dependency injection."""

from typing import Annotated
from collections.abc import AsyncIterator

from fastapi import Depends

from bluddit_api.database import Database, get_database, get_optional_database
from bluddit_api.repositories.auth import AuthRepository
from bluddit_api.repositories.health import HealthRepository
from bluddit_api.repositories.membership import MembershipRepository


async def get_auth_repository(
    database: Database = Depends(get_database),
) -> AuthRepository:
    return AuthRepository(database)


async def get_health_repository(
    database: Database | None = Depends(get_optional_database),
) -> HealthRepository | None:
    return HealthRepository(database) if database is not None else None


AuthRepositoryDep = Annotated[AuthRepository, Depends(get_auth_repository)]
HealthRepositoryDep = Annotated[HealthRepository | None, Depends(get_health_repository)]


async def get_membership_repository(
    database: Database = Depends(get_database),
) -> AsyncIterator[MembershipRepository]:
    # One transaction for every SQL operation composed by the membership route.
    async with database.transaction() as connection:
        yield MembershipRepository(connection)


MembershipRepositoryDep = Annotated[
    MembershipRepository, Depends(get_membership_repository, scope="function")
]
