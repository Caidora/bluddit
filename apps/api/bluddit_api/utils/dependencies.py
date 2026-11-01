"""Repository providers for request dependency injection."""

from typing import Annotated

from fastapi import Depends, Request, HTTPException

from bluddit_api.repositories.bluds import BludsRepository
from bluddit_api.repositories.oauth import OAuthRepository
from bluddit_api.repositories.events import EventsRepository

from bluddit_api.models.bluds import BludReferenceData
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


async def get_events_repository(
    database: Database = Depends(get_database),
) -> EventsRepository:
    return EventsRepository(database)


EventsRepositoryDep = Annotated[EventsRepository, Depends(get_events_repository)]


async def get_reference_data(request: Request) -> BludReferenceData:
    if request.app.state.references is None:
        raise HTTPException(503, "Database unavailable")
    return await request.app.state.references.snapshot()


ReferencesDep = Annotated[BludReferenceData, Depends(get_reference_data)]


async def get_oauth_repository(
    database: Database = Depends(get_database),
) -> OAuthRepository:
    return OAuthRepository(database)


OAuthRepositoryDep = Annotated[OAuthRepository, Depends(get_oauth_repository)]
