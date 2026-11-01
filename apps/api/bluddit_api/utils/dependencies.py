"""Repository providers for request dependency injection."""

from typing import Annotated

from fastapi import Depends

from bluddit_api.repositories.bluds import BludsRepository

from bluddit_api.database import Database, get_database, get_optional_database
from bluddit_api.repositories.handbook import HandbookRepository
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
) -> MembershipRepository:
    return MembershipRepository(database)


MembershipRepositoryDep = Annotated[
    MembershipRepository, Depends(get_membership_repository)
]


async def get_handbook_repository(
    database: Database = Depends(get_database),
) -> HandbookRepository:
    return HandbookRepository(database)


HandbookRepositoryDep = Annotated[HandbookRepository, Depends(get_handbook_repository)]


async def get_bluds_repository(
    database: Database = Depends(get_database),
) -> BludsRepository:
    return BludsRepository(database)


BludsRepositoryDep = Annotated[BludsRepository, Depends(get_bluds_repository)]
