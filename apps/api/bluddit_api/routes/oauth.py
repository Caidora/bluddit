"""Server-only OAuth callback; no provider code or token reaches the SPA."""

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from psycopg.errors import UniqueViolation

from bluddit_api.repositories.oauth import LinkingConflict
from bluddit_api.routes.auth import set_flow_cookie, clear_flow_cookie
from bluddit_api.utils.auth import set_refresh_cookie
from bluddit_api.utils.battlenet import (
    FLOW_COOKIE,
    REGISTRATION_COOKIE,
    ProviderError,
    provider,
)
from bluddit_api.utils.dependencies import AuthRepositoryDep, OAuthRepositoryDep
from bluddit_api.utils.security import MembershipState, new_token, token_hash

router = APIRouter()


def redirect(request: Request, path: str) -> RedirectResponse:
    response = RedirectResponse(path, status_code=303)
    clear_flow_cookie(response, FLOW_COOKIE, request)
    clear_flow_cookie(response, REGISTRATION_COOKIE, request)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/api/oauth-redirect", response_class=RedirectResponse, status_code=303)
async def callback(
    request: Request, repository: OAuthRepositoryDep, auth: AuthRepositoryDep
):
    states, codes = (
        request.query_params.getlist("state"),
        request.query_params.getlist("code"),
    )
    hashed = token_hash(states[0]) if len(states) == 1 else None
    browser = token_hash(request.cookies.get(FLOW_COOKIE))
    attempt = (
        await repository.consume_attempt(hashed, browser)
        if hashed and browser
        else None
    )
    if attempt is None:
        return redirect(request, "/login?authError=expired")
    if (
        request.query_params.get("error")
        or len(codes) != 1
        or not codes[0]
        or len(codes[0]) > 4096
    ):
        return redirect(request, "/login?authError=cancelled")
    try:
        async with request.app.state.oauth_slots:
            identity = await provider(request).exchange(codes[0])
        account = await repository.authenticate(attempt, identity)
    except ProviderError:
        return redirect(request, "/login?authError=provider")
    except (UniqueViolation, LinkingConflict):
        return redirect(request, "/login?authError=link_conflict")
    if account is None:
        registration = new_token()
        await repository.create_registration(token_hash(registration), identity)
        response = redirect(request, "/register/complete")
        set_flow_cookie(response, REGISTRATION_COOKIE, registration, request)
        return response
    if account.membership_state == MembershipState.PENDING:
        return redirect(request, "/pending-approval")
    if account.membership_state != MembershipState.ACTIVE:
        return redirect(request, "/login?authError=membership")
    refresh = new_token()
    expiry = await auth.create_session(
        account.id, identity.token_expires_at, token_hash(refresh)
    )
    if expiry is None:
        return redirect(request, "/login?authError=membership")
    response = redirect(
        request, "/auth/complete?" + urlencode({"returnTo": attempt.return_to})
    )
    set_refresh_cookie(response, refresh, request.app.state.auth_settings, expiry)
    return response
