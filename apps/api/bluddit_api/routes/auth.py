"""Login, refresh, logout, and current-account HTTP routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from starlette.concurrency import run_in_threadpool

from bluddit_api.database import Database, get_database
from bluddit_api.repositories.auth import AuthRepository
from bluddit_api.utils.auth import (
    COOKIE_NAME,
    TOKEN_PATH,
    access_response,
    current_account,
    set_refresh_cookie,
    unauthorized,
)
from bluddit_api.utils.security import (
    MembershipState,
    DUMMY_HASH,
    new_token,
    normalize_username,
    token_hash,
    verify_password,
)

router = APIRouter(prefix="/api/auth")


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(max_length=256)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def username_format(cls, value):
        return normalize_username(value)


@router.post("/login")
async def login(
    body: LoginInput,
    request: Request,
    response: Response,
    database: Database = Depends(get_database),
):
    await request.app.state.login_throttle.reserve(body.username)
    repository = AuthRepository(database)
    account = await repository.account_credentials(body.username)
    # Bound memory-intensive password work even across many different usernames.
    async with request.app.state.password_slots:
        valid = await run_in_threadpool(
            verify_password,
            account["password_hash"] if account else DUMMY_HASH,
            body.password.get_secret_value(),
        )
    if (
        not valid
        or account is None
        or account["membership_state"] != MembershipState.ACTIVE
    ):
        raise HTTPException(401, "Invalid username or password")
    refresh, access = new_token(), new_token()
    created = await repository.create_session(
        account["id"],
        account["password_hash"],
        token_hash(refresh),
        token_hash(access),
    )
    if not created:
        raise HTTPException(401, "Invalid username or password")
    set_refresh_cookie(response, refresh, request.app.state.auth_settings)
    return access_response(access)


@router.post("/token")
async def refresh(
    request: Request, response: Response, database: Database = Depends(get_database)
):
    hashed = token_hash(request.cookies.get(COOKIE_NAME))
    if hashed is None:
        raise unauthorized()
    replacement, access = new_token(), new_token()
    rotated = await AuthRepository(database).rotate_session(
        hashed,
        token_hash(replacement),
        token_hash(access),
    )
    if not rotated:
        raise unauthorized()
    set_refresh_cookie(response, replacement, request.app.state.auth_settings)
    return access_response(access)


@router.delete("/token", status_code=204)
async def logout(request: Request, database: Database = Depends(get_database)):
    hashed = token_hash(request.cookies.get(COOKIE_NAME))
    if hashed is not None:
        await AuthRepository(database).revoke_session(hashed)
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE_NAME,
        path=TOKEN_PATH,
        secure=request.app.state.auth_settings.secure,
        httponly=True,
        samesite="strict",
    )
    return response


@router.get("/me")
async def me(account=Depends(current_account)):
    return account
