"""Legacy proof for migration, verified signup, and local session HTTP routes."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from psycopg.errors import UniqueViolation
from starlette.concurrency import run_in_threadpool

from bluddit_api.models.accounts import Account, AccountCredentials
from bluddit_api.repositories.oauth import OAuthRepository
from bluddit_api.routes.responses import (
    AccountResponse,
    AccessTokenResponse,
    CurrentAccountResponse,
)
from bluddit_api.utils.dependencies import AuthRepositoryDep, OAuthRepositoryDep
from bluddit_api.utils.permissions import RolePolicy
from bluddit_api.utils.auth import (
    COOKIE_NAME,
    TOKEN_PATH,
    ACCESS_SECONDS,
    current_account,
    set_refresh_cookie,
    unauthorized,
)
from bluddit_api.utils.battlenet import (
    FLOW_COOKIE,
    REGISTRATION_COOKIE,
    FLOW_SECONDS,
    provider,
    safe_return,
)
from bluddit_api.utils.security import (
    DUMMY_HASH,
    new_token,
    normalize_username,
    token_hash,
    verify_password,
)

router = APIRouter(prefix="/api/auth")


class StartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    return_to: str | None = Field(default=None, max_length=2048)


class LoginInput(StartInput):
    username: str = Field(max_length=256)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def username_format(cls, value):
        return normalize_username(value)


class AuthorizationResponse(BaseModel):
    authorization_url: str


class RegistrationContextResponse(BaseModel):
    battletag: str


class RegistrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def display_name_format(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Display name is required")
        return value


def set_flow_cookie(response: Response, name: str, value: str, request: Request):
    response.set_cookie(
        name,
        value,
        max_age=FLOW_SECONDS,
        path="/api",
        httponly=True,
        secure=request.app.state.auth_settings.secure,
        samesite="lax",
    )


def clear_flow_cookie(response: Response, name: str, request: Request):
    response.delete_cookie(
        name,
        path="/api",
        httponly=True,
        secure=request.app.state.auth_settings.secure,
        samesite="lax",
    )


async def begin(
    request: Request,
    response: Response,
    repository: OAuthRepository,
    return_to: str | None,
    account: AccountCredentials | None = None,
) -> AuthorizationResponse:
    client = provider(request)
    state, browser = new_token(), new_token()
    await repository.create_attempt(
        token_hash(state), token_hash(browser), safe_return(return_to), account
    )
    set_flow_cookie(response, FLOW_COOKIE, browser, request)
    clear_flow_cookie(response, REGISTRATION_COOKIE, request)
    return AuthorizationResponse(authorization_url=client.authorization_url(state))


@router.post("/battlenet/start")
async def start(
    body: StartInput,
    request: Request,
    response: Response,
    repository: OAuthRepositoryDep,
) -> AuthorizationResponse:
    await request.app.state.oauth_throttle.reserve("oauth")
    return await begin(request, response, repository, body.return_to)


@router.post("/login")
async def login(
    body: LoginInput,
    request: Request,
    response: Response,
    repository: AuthRepositoryDep,
    oauth_repository: OAuthRepositoryDep,
) -> AuthorizationResponse:
    await request.app.state.login_throttle.reserve(body.username)
    account = await repository.get_account_credentials(body.username)
    encoded = (
        account.password_hash
        if account and account.password_hash and account.battle_net_account_id is None
        else DUMMY_HASH
    )
    async with request.app.state.password_slots:
        valid = await run_in_threadpool(
            verify_password, encoded, body.password.get_secret_value()
        )
    if (
        not valid
        or account is None
        or not account.password_hash
        or account.battle_net_account_id is not None
    ):
        raise HTTPException(401, "Invalid username or password")
    return await begin(request, response, oauth_repository, body.return_to, account)


@router.get("/battlenet/registration")
async def registration_context(
    request: Request, repository: OAuthRepositoryDep
) -> RegistrationContextResponse:
    hashed = token_hash(request.cookies.get(REGISTRATION_COOKIE))
    registration = await repository.get_registration(hashed) if hashed else None
    if registration is None:
        raise HTTPException(401, "Sign in with Battle.net again to request membership")
    return RegistrationContextResponse(battletag=registration.battletag)


@router.post("/register", status_code=201)
async def register(
    body: RegistrationInput,
    request: Request,
    response: Response,
    repository: OAuthRepositoryDep,
) -> AccountResponse:
    await request.app.state.registration_throttle.reserve("registration")
    hashed = token_hash(request.cookies.get(REGISTRATION_COOKIE))
    if hashed is None:
        raise HTTPException(401, "Sign in with Battle.net again to request membership")
    try:
        account = await repository.register(hashed, body.display_name)
    except UniqueViolation:
        raise HTTPException(
            409, "This Battle.net account is already linked. Sign in again."
        ) from None
    if account is None:
        raise HTTPException(401, "Sign in with Battle.net again to request membership")
    clear_flow_cookie(response, REGISTRATION_COOKIE, request)
    return AccountResponse.model_validate(account)


@router.post("/token")
async def refresh(
    request: Request, response: Response, repository: AuthRepositoryDep
) -> AccessTokenResponse:
    hashed = token_hash(request.cookies.get(COOKIE_NAME))
    if hashed is None:
        raise unauthorized()
    replacement, access = new_token(), new_token()
    expiry = await repository.rotate_session(
        hashed, token_hash(replacement), token_hash(access)
    )
    if expiry is None:
        raise unauthorized()
    remaining = int((expiry - datetime.now(timezone.utc)).total_seconds())
    if remaining < 1:
        raise unauthorized()
    set_refresh_cookie(response, replacement, request.app.state.auth_settings, expiry)
    return AccessTokenResponse(
        access_token=access, expires_in=min(ACCESS_SECONDS, remaining)
    )


@router.delete("/token", status_code=204)
async def logout(request: Request, repository: AuthRepositoryDep) -> Response:
    hashed = token_hash(request.cookies.get(COOKIE_NAME))
    if hashed is not None:
        await repository.revoke_session(hashed)
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE_NAME,
        path=TOKEN_PATH,
        secure=request.app.state.auth_settings.secure,
        httponly=True,
        samesite="strict",
    )
    clear_flow_cookie(response, FLOW_COOKIE, request)
    clear_flow_cookie(response, REGISTRATION_COOKIE, request)
    return response


@router.get("/me")
async def me(
    account: Annotated[Account, Depends(current_account)],
) -> CurrentAccountResponse:
    public_account = AccountResponse.model_validate(account)
    return CurrentAccountResponse(
        **public_account.model_dump(),
        permissions=sorted(RolePolicy.permissions(account.role_name)),
    )
