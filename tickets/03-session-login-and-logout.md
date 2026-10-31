# 03: Session login and logout

Status: In progress — implemented and locally verified; PR review, CI, deployment, and production acceptance pending

Dependencies: Ticket 02.

## Outcome

Allow approved accounts to authenticate with server-managed sessions.

## Implementation

- Implement login, logout, and current-account endpoints, plus authenticated request dependencies.
- Validate credential input and session-token format/hash generation in the application layer.
- Use established password hashing and cryptographically random opaque session tokens. Store only token hashes in PostgreSQL.
- Set secure production cookie attributes, an explicit expiry, and session rotation on login. Revoke the session on logout.
- Protect state-changing requests against CSRF and reject disallowed origins. Add basic login throttling and generic login errors.
- Keep inactive or unapproved accounts out of member endpoints.
- Provide an administrative CLI for creating the first officer account and resetting a password, without logging secrets. No email service is required.

## Acceptance and verification

Correct credentials create a session; wrong credentials fail. Expired, revoked, inactive-account, and missing sessions fail. Cross-site mutation attempts fail. Logout invalidates the token at the server.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

Implemented opaque 10-minute bearer access tokens and rotating HttpOnly refresh
cookies with a sliding 30-day expiry. Added login, refresh, logout, current-account
routes and a reusable active-account dependency. Each login is an independent
session. Earlier access tokens survive refresh until expiry; parent-session checks
make logout and password resets immediately effective. No JWTs or frontend screens
are included; account screens and the client contract are documented for ticket 05.

As explicitly agreed: store only the current refresh hash, with no refresh-token
history, replay-triggered revocation, grace window, absolute session lifetime, or
existing-session conversion. A stale refresh returns 401 without changing cookies
or revoking valid tokens. Atomic hash replacement permits exactly one concurrent
exchange. Migration 0002 adds refresh sessions and a required parent reference on
access sessions, assuming the existing sessions table is empty. Migration 0001 is
unchanged. Rolling back to the previous health-only image leaves the additive
schema intact and is compatible.

Added Argon2id through argon2-cffi 25.1.0 and the updated lockfile. Login has generic
errors, concurrency-limited password verification, and application-memory throttling
(10 attempts/username/15 minutes, bounded counters, 429/Retry-After). Counters reset
on restart and are process-local; shared throttling is required before scaling.
Unsafe API requests require an allowed Origin and CSRF header. Refresh cookies are
host-only, HttpOnly, SameSite=Strict, scoped to /api/auth/token and Secure in
production. Auth responses disable caching and validation errors omit input values.

Added hidden-prompt administrative CLI commands for first-officer creation and
password reset. Bootstrap is serialized and refuses a second active officer;
password reset preserves role/membership and revokes every account session.
Interactive production administration over SSH is the user-approved exception to
Actions-only mutations. Setup, API usage, origins, recovery, compatibility, and the
ticket 05 memory-only/cross-tab token coordination contract are in the runbook.

Started from main `0115da89cdf38bacf58d3e40bb97d7b9460f3f00`; its predecessor
[production workflow 41179987176](https://github.com/Caidora/bluddit/actions/runs/41179987176)
passed verify, publish, and production jobs after the ticket 02 deployment fix.

Local verification on 2026-10-31:

- `make verify` with a dedicated disposable PostgreSQL database: passed frontend
  type checks/build, 11 API/unit checks, 15 PostgreSQL integration checks, 18
  infrastructure checks, and base/reload Compose configuration validation.
- `actionlint .github/workflows/ci.yaml` and `git diff --check`: passed.
- Isolated production API/web container builds: passed with locked dependencies.
- Isolated Compose stack with APP_ENV=production: migrations applied, rerun reported
  no changes, readiness and SPA/API smoke passed on port 18084. The Nginx bind
  configuration was copied unchanged into /private/tmp for Docker Desktop access.
- HTTP checks against those production images passed login, Secure/HttpOnly cookie
  attributes, rotation, stale-token rejection without cookie mutation or session
  revocation, surviving access tokens, origin rejection, and server-side logout.
- Integration tests cover concurrent refresh, expiry/revocation/membership gating,
  reset across devices, bootstrap concurrency, throttling, and sanitized DB failures.

Pending: required maintainer PR approval, CI on the implementation branch, merge
and Actions deployment, and public HTTPS acceptance using dedicated test records.
No ticket 03 production verification has happened; do not mark Complete yet.
