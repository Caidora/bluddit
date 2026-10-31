# Development and production operations

## Selected versions

Node 24 LTS (see `.nvmrc`), React Router 8.5.1 framework SPA mode with CSR (`ssr: false`),
React 19.3.1, Vite 8.3.5, TypeScript 7.0.2, Python 3.13, uv 0.6.13,
FastAPI 0.162.0, Uvicorn 0.54.0, pytest 9.2.0, and HTTPX 0.28.1.
The npm and uv lockfiles record all resolved dependencies. CI installs from them.
Build/development containers use Node 24/Python 3.13 Debian Bookworm slim.
Production serves the static frontend with stable Alpine Nginx as UID 1000,
alongside the Python API, PostgreSQL 17 Bookworm, and the Nginx reverse proxy. Production resolves and tests immutable image digests.
Base-image patch updates are picked up by a new build, not by restarting a release.

The Python PostgreSQL driver is **Psycopg 3.3.6** (binary distribution), with
**psycopg-pool 3.3.3**, explicit parameterized SQL, and no ORM. Numbered SQL
migrations introduce accounts, roles, and sessions. Role permissions are defined
in Python; migration 0003 removes the obsolete database permission tables.

## Frontend rendering

The frontend uses [React Router SPA mode](https://reactrouter.com/how-to/spa).
`npm run build` generates `apps/web/build/client`; production serves only these
static files with Nginx on port 3000, without a Node application server.
Nginx falls back to `index.html` for frontend routes so direct links and refreshes
work. Missing assets return 404. The outer proxy continues routing `/api/` to FastAPI.
Development uses the React Router/Vite development server on the same port.

Use browser-side fetching or `clientLoader`/`clientAction` for API calls; backend
logic, authentication, and authorization live in FastAPI. React Router generates
the loading shell at build time, so keep the root's initial render safe to execute
without browser globals. `@react-router/node` is retained for this build step.

The HTTP smoke check validates the SPA shell, referenced assets, route fallback,
and API health; it does not execute JavaScript or verify the rendered page UI.

## Fresh checkout

Install Docker with the Compose plugin (v2 or newer). Copy `.env.example` to `.env`, set a local
`POSTGRES_PASSWORD`, then run:

```sh
make up
python3 infra/smoke.py http://127.0.0.1:8080
```

This builds production containers; host Node and uv are not required to run them.
The web page and `/api/health` share the same origin. PostgreSQL has no published
port. Swagger UI is publicly available at `/api/docs` in all environments,
including production, with its OpenAPI schema at `/api/openapi.json`. Both paths
use the existing Nginx `/api/` proxy. JSON route responses have dedicated Pydantic
models in `apps/api/bluddit_api/routes/responses.py`, documented in OpenAPI. Routes
convert repository records to these public models before returning them; only the
declared public fields are serialized. Logout returns an empty 204 response. API operations retain their session,
permission, and origin/CSRF checks; write requests require `X-CSRF-Protection: 1`
and an allowed origin. `/api/health` checks process liveness; `/api/ready`
checks database access and required migrations without exposing configuration.

For source reload, use `make dev`. To run checks on the host, install Node 24,
Python 3.13, uv 0.6.13, and Make, then `make setup`. Before `make verify`, set
`TEST_DATABASE_URL` to a disposable PostgreSQL database ending in `_test`. The
connection user must be able to create databases; each test creates and removes
only its own randomly named test database. No application credentials are used as
a fallback. `make api-test` runs the database-independent API checks separately.
Use `nvm use` if your default Node version is different. If port 8080 is occupied,
set `LOCAL_PORT=18081` in `.env`, or prefix the command with that variable.
Use the matching URL for the smoke check. Local defaults bind to loopback.

| Action | Command |
| --- | --- |
| Install locked host dependencies | `make setup` |
| Production-style local stack | `make up` |
| Local source reload | `make dev` |
| Stop containers, preserve data | `make down` |
| Follow local logs | `make logs` |
| Web types / production build | `make web-check` / `make web-build` |
| API / database / deployment tests | `make api-test` / `make db-test` / `make infra-test` |
| Apply migrations / inspect status | `make migrate` / `make migration-status` |
| Validate Compose configuration | `make config` |
| All host checks | `make verify` |

Use Ruff for Python formatting and linting (`uv tool install ruff` if needed).
Before committing or handing off Python changes, run `ruff format` on all changed
Python files, then run `ruff format --check` and `ruff check` against the same
paths, including changed tests and infrastructure scripts. Finish with
`make verify` and `git diff --check`; fix any failures and review automatic edits.
For a full Python-tree check, the paths are `apps/api infra`. Ruff is not currently
included in `make verify` or CI; these commands must be run explicitly. See the
[contribution guide](../contributions.md#set-up-and-verify-locally) for the final
check sequence. Documentation-only changes still use documentation checks.

The local volume is `bluddit-local_postgres_data`. Never use `down --volumes` on
data you want to keep. Changing `POSTGRES_PASSWORD` after initialization does not
rotate the existing PostgreSQL account password.

## GitHub configuration

All production writes happen through **CI and production deployment** in Actions.
Pull requests and `main` pushes run the same host checks as local development and
smoke-test production containers. Successful `main` builds publish multi-platform
GHCR images, smoke-test their exact digests, and then deploy those digests.
Push-triggered runs are restricted to `main`; feature branches run CI through pull
requests. Image publication and production operations require
`main`, including manual workflow runs.

Deployment settings are **repository-level Actions secrets**, matching the actual
repository setup. No GitHub environment or extra registry PAT is required.

| Secret | Value |
| --- | --- |
| `DEPLOY_HOST` | Existing Hetzner SSH hostname/IP |
| `DEPLOY_USER` | Deployment user; root or non-interactive sudo is required for initial host setup |
| `DEPLOY_PORT` | Numeric SSH port |
| `DEPLOY_PATH` | Absolute application directory, e.g. `/opt/bluddit`; no shell expressions |
| `APP_DOMAIN` | Confirmed hostname only, without scheme/path |
| `TLS_EMAIL` | Let's Encrypt contact email |
| `POSTGRES_PASSWORD` | Strong nonempty database password, no line breaks |
| `SSH_KEY` | Complete private key, with original line breaks |
| `SSH_KNOWN_HOSTS` | Independently verified SSH host entries for the configured address/port |

The automatic `GITHUB_TOKEN` authenticates publishing and temporary server pulls.
Missing secrets fail before remote changes. SSH always uses strict host-key
verification. Neither credential values nor raw server diagnostics are printed.

Before first deployment, confirm DNS A/AAAA records reach this server and public TCP 80/443 are permitted
by the Hetzner and host firewalls. SSH must be reachable from GitHub-hosted runners.
On an apt/systemd host the deployment installs missing Docker, Nginx,
and Certbot packages. When Compose is missing, it installs Docker's official
Compose 5.6.1 CLI plugin after verifying its pinned SHA-256 checksum (amd64/arm64).
Existing installations are reused; unrelated packages and
services are not upgraded or removed. Other package managers require prerequisites
to be provisioned first through a reviewed CI/CD host-setup change.

An existing non-Nginx ingress, an unmanaged virtual host for `APP_DOMAIN`, or an
unmanaged Bluddit volume blocks deployment with an explicit integration error.
Do not remove another service to work around that error. Inspect it privately and
make a reviewed CI/CD integration change. Existing unrelated Nginx hosts remain.

## Server layout and ownership

The confirmed connection settings and root directory are stored in the secrets
above. Their values are intentionally absent from this public repository.
The root-owned layout below is relative to `DEPLOY_PATH`:

```text
deploy.lock                  # host-side nonblocking operation lock
shared/postgres_password     # mode 0600, never in a release or backup artifact
shared/api_postgres_password # same credential, mode 0400, owned by UID/GID 10001
releases/<commit>-<run-id>/   # immutable manifest, Compose config, Nginx config, tool
current -> releases/...      # latest release that passed health checks
previous -> releases/...     # preceding successful release
backups/*.dump               # mode 0600; local PostgreSQL custom-format backups
```

Production uses Compose project `bluddit` and external volume
`bluddit_postgres_data`. Containers restart unless stopped. Database: `bluddit`;
database user: `bluddit`. Only the container Nginx port is published, on
`127.0.0.1:18080`. Web port 3000, API port 8000, and database port 5432 remain
inside the Compose network. Host Nginx exposes 80/443 using a dedicated managed
`/etc/nginx/conf.d/bluddit.conf`. Certificates live under Let's Encrypt's normal
hostname directory; ACME uses `/var/lib/bluddit-acme`. Certbot's timer renews them,
and its deployment hook validates and reloads Nginx.

## Deploy, redeploy, verify, and restart

Merge a verified change to `main` for automatic deployment. Alternatively, dispatch
**CI and production deployment** on **main**, selecting `deploy`. That reruns all
checks and publishes/deploys the selected `main` commit. Deployment from feature
branches is disabled. Operations are serialized and never cancel an active deploy.

Release IDs are `<full-commit-SHA>-<workflow-run-ID>`. Workflow summaries contain
the candidate release and image references. A `deployment-images` artifact records
the tested image digests and release ID without host settings or credentials.
The remote `current` reference only
advances after internal and public HTTPS checks pass and `healthy.json` records
successful verification. Rollback refuses releases without that record.
Health clients identify themselves as `Bluddit-Healthcheck/1.0`; the site's CDN
rejects Python's default user agent. TLS verification remains enabled.
A failed operation reports a
failure without printing private host diagnostics. Review Actions first, then read
server journal/container logs privately. Do not paste raw server logs into public
issues or workflow logs; they may contain sensitive details once features arrive.

Dispatch `restart` to restart current containers and check health. Dispatch `verify`
to check that application/database ports are private, create an isolated disposable probe table, restart all containers, check the
probe survived, remove it, and create/restore-test a backup. It does not change
member records. Verify operations briefly interrupt the application.

If a rollout fails after container replacement, `current` still points to the last
successful release; the failed containers may be running. Dispatch rollback to
that recorded release. A manual operation must be selected from the `main` branch.

## Image rollback

Dispatch **CI and production deployment**, select `rollback`, and supply the exact
previous successful release ID. The workflow pulls its recorded digests, starts
that release, checks health, and updates successful-release references. No images
are rebuilt and no database volume is removed. Keep GHCR versions referenced by
release manifests; no image or volume pruning is automated.

Automatic image rollback refuses a different PostgreSQL image digest. Database
compatibility requires review, even when the major version is unchanged.
Image rollback never undoes schema. The initial account/session migration is
additive and compatible with the foundation image. Later migrations require
explicit compatibility assessment before selecting an older application image.
Rollback and restart never invoke the migration service. The host verifies the
selected release's health contract; an older foundation release does not require
the new readiness endpoint.

## Database backup

The normal operator command is:

```sh
gh workflow run ci.yaml --ref main -f operation=backup
```

The workflow uses `pg_dump -U bluddit -d bluddit -Fc` inside the database container,
then restores the dump into a uniquely named disposable database with
`pg_restore --exit-on-error`. It drops only that disposable database and marks the
backup complete after success. Partial failures are not retained as valid dumps.
Backups stay under `DEPLOY_PATH/backups`; they are not uploaded to public Actions
artifacts. Restrict access and copy them to approved off-host storage. Automated
retention and full disaster recovery are covered by ticket 18; a backup on this
server alone cannot protect against loss of the server.

To diagnose privately with existing SSH access, resolve `DEPLOY_PATH/current` and
run Docker Compose there with `--env-file release.env -f compose.production.yaml`.
Read-only `ps` and `logs --tail=100` are useful. Perform production mutations via
Actions, keeping workflow and release evidence together. Interactive account
bootstrap and password recovery are the exception documented below.

## Database access and migrations

Local Compose starts the database, runs a one-shot `migrate` service, and starts
the API only after migration success. Both `make up` and `make dev` use this order.
`make migrate` builds and applies pending migrations; `make migration-status`
reports pending migrations against a running local database. Neither command
removes database volumes. Restarting an API process does not migrate the database.

The API and migration CLI use `PGHOST`, `PGPORT` (default 5432), `PGDATABASE`,
`PGUSER`, and exactly one of `PGPASSWORD` or `PGPASSWORD_FILE`. Compose maps local
`POSTGRES_*` settings to these values. Production uses mounted secrets: the
existing database password remains root-owned, and a separate identical file is
owned by UID/GID 10001 so the non-root API can read it. File-backed Compose secrets
retain host ownership. Do not print connection settings or dump Compose's expanded
configuration into logs. Production requires database configuration at startup;
missing local configuration leaves process health working and readiness at 503.

One async pool per API process has 1–5 connections and a three-second acquisition/query
timeout. API startup opens it without waiting for the database, so process health
remains available during outages. Routes live in `bluddit_api/routes`; use
`async def` endpoints with reusable `Annotated` repository dependency aliases
such as `repository: AuthRepositoryDep` and `repository: HealthRepositoryDep`.
Providers in `bluddit_api/utils/dependencies.py` construct repositories using `Depends(get_database)`; routes and authentication
helpers receive repositories instead of database connections. Readiness uses an
optional repository so an unconfigured database still returns its existing 503 response.
Application SQL belongs in `bluddit_api/repositories`. Membership repository
methods represent full persistence operations and can execute several queries
in their own transaction, without chaining repository helpers. The provider
constructs the repository with the shared Database; there is no request-wide
transaction. API handlers perform permission and input/transition checks before
calling the operation. Those checks may race with other requests. SQL predicates
still reject conflicting transitions and protect leadership records. Membership
updates and session revocation commit separately. Rejection/deactivation routes
call the reusable auth repository revocation operation after the membership update.
If revocation fails, the API returns 503 but the membership change remains committed.
Inactive/rejected accounts are still denied immediately by live membership checks;
reactivating before successful revocation can restore old sessions. Concurrent
reactivation/login can also race with revocation. These tradeoffs are accepted. GM succession locks the
affected accounts, rechecks the current active GM, and performs both role updates in one
transaction. Each method commits before returning success. Handlers do not execute
SQL or manage connections. Existing
auth/account-recovery repositories retain their transaction boundaries and static
helpers; this ticket does not refactor those unrelated operations.
Keep each query in one triple-quoted string and bind values using named
placeholders such as `%(account_id)s` with a separate mapping such as
`{"account_id": account_id}`. Do not use positional `%s` placeholders or parameter
sequences, and do not interpolate values into SQL. Await execution and cursor fetch operations.
Each business operation commits on success and rolls back on error; refresh
rotation/access issuance and password reset/session revocation remain atomic.
Shared authentication configuration, dependencies, and credential/token helpers
live in `bluddit_api/utils`. Pool lifecycle and migration tooling remain separate
infrastructure modules. The migration CLI also uses async connections. No SQL
string interpolation or ORM is used.

ID columns use the singular table/entity name plus `_id`, for example
`accounts.account_id` and `refresh_sessions.refresh_session_id`, rather than a
bare `id`. Foreign-key IDs use the referenced entity's prefix, so
`sessions.account_id` references `accounts.account_id`. Keep natural/composite
keys where appropriate; this rule does not require adding surrogate IDs.
Existing bare `id` columns remain unchanged until
[ticket 21](../tickets/21-table-prefixed-id-columns.md) is implemented.

Each account has one required role (default `member`).
The seeded roles are Guild Master (`guild_master`), Officer (`officer`), and Member
(`member`). Accounts inherit all permissions from their single role; there are no
direct account grants. `utils/permissions.py` defines the fixed Python policy;
there is no startup synchronization or database override. Migration 0003 drops
`role_permissions` and `permissions`, retaining the referenced `roles` table.
Organizer and quartermaster assignments and attribute checks arrive with the
feature tickets that introduce their resources. See [the permission matrix](permissions.md).

Username formatting, membership-state validation, and token-hash-length validation
belong to the application endpoints in tickets 03–04. The migration retains
case-insensitive username uniqueness and foreign keys.

Migrations live inside the API package as `NNNN_description.sql`, starting at
`0001`. Use `python -m bluddit_api.migrate status` or `apply` from the API environment.
The runner holds a database advisory lock, verifies the ledger's filenames and
SHA-256 checksums, and executes each pending migration and its ledger entry in
one transaction. Only forward, transactional SQL is supported: do not include
transaction-control statements or operations requiring autocommit. During PR
review, edit the existing migration while it has not run in production. Once a
migration has run in production, preserve its contents/checksum and add a new
numbered migration for changes. Local/CI execution alone does not require a new
migration. If an edited migration has run locally, recreate only that disposable
development/test database; do not alter the ledger to bypass checksum validation
or reset production/member data. A failed migration rolls back its own changes;
earlier successful migrations remain applied.
A retry safely skips successful migrations. Unexpected migration history or edited
applied files blocks deployment until the compatible files/image are restored.

Production deployment pulls the candidate image, ensures PostgreSQL is healthy,
checks migration status, and creates/restores a backup before any pending schema
changes (including the initial migration). It then runs the profiled migration
service once before application rollout. Backup or migration failure prevents API
replacement and leaves the successful release reference unchanged. Readiness and
internal/public smoke checks must pass before recording the candidate as healthy.
Do not restore a backup automatically over member changes after a rollout failure;
use a compatible image rollback and assess schema recovery separately.

CI uses disposable PostgreSQL for three behavioral checks: migration/readiness
and safe rerun, application transaction rollback, and failed migration rollback.
Container verification also runs migrations twice before checking readiness,
including the exact published images. There are no per-column or schema snapshot
tests. Production verification and migration reruns must happen through Actions.

## Authentication and account recovery (ticket 03)

The API uses opaque bearer access tokens lasting 600 seconds and rotating refresh
cookies lasting 30 days from the latest login/refresh. Only SHA-256 token hashes
are stored. Each refresh replaces the current refresh hash and creates another
access token; earlier access tokens retain their normal expiry. No refresh-token
history or replay-triggered revocation is implemented. A reused/invalid refresh
token returns 401 without changing the cookie or valid session. Concurrent refresh
attempts with the same token have exactly one winner. A lost successful response
may require signing in again.

| Endpoint | Request / result |
| --- | --- |
| `POST /api/auth/login` | JSON `username`, `password`; returns `access_token`, `token_type: Bearer`, `expires_in: 600` and sets the refresh cookie |
| `POST /api/auth/token` | Refresh cookie; rotates it and returns the same access-token shape |
| `DELETE /api/auth/token` | Revokes the refresh session (invalidating all its access tokens), clears the cookie, returns 204; safe to repeat |
| `GET /api/auth/me` | `Authorization: Bearer <access_token>`; returns `id`, `username`, `display_name`, `membership_state`, `role_name`, `timezone`, and sorted effective `permissions` |

Only `active` accounts authenticate. `pending`, `rejected`, and `inactive` cannot
log in, refresh, or use existing access tokens. Request-time account and parent
session checks enforce immediate logout, deactivation, and password-reset effects.
New logins are independent sessions; resetting a password invalidates every device.
Registration and membership administration are available through the API described
below. Account screens arrive in ticket 05. Bootstrap does not write permission mappings.

Set `AUTH_ALLOWED_ORIGINS` to comma-separated exact origins (scheme, hostname,
and optional port, no trailing slash). All unsafe `/api/` requests require an
allowed `Origin` plus `X-CSRF-Protection: 1`. Login and registration accept JSON only and have an
8 KiB body limit. CORS credentials are not enabled. Local Compose defaults to
`http://localhost:LOCAL_PORT` and `http://127.0.0.1:LOCAL_PORT`; override the setting
for a different development origin. A directly run API needs the setting too.
Production requires explicit HTTPS origins; the deployment writes
`AUTH_ALLOWED_ORIGINS=https://APP_DOMAIN` into each release's `release.env`.
All API responses use `Cache-Control: no-store`. Do not log
request bodies, cookies, bearer tokens, or passwords.

The `bluddit_refresh` cookie is HttpOnly, SameSite=Strict, host-only, and scoped to
`/api/auth/token`. It has explicit 30-day Max-Age/Expires and is Secure in
production. Invalid refresh requests never clear it. Every unsafe request still
requires origin/CSRF checks. A bearer token cannot be substituted for the cookie
on refresh/logout, and the cookie does not authenticate member endpoints.

Login attempts are limited in application memory to 10 per normalized username
per fixed 15-minute window, including successful attempts. Limits return 429 and
`Retry-After`. Up to 10,000 active username counters are retained; when full, new
keys are rejected until space expires. Counter reservation is concurrency-safe;
expired counters are cleaned as requests arrive. Restart clears counters, and
limits apply per process. Run one API worker/replica until shared counters are
introduced. Registration has a separate process-wide bucket of 10 attempts per
15 minutes, including duplicates and successes; changing usernames does not bypass
it. This deliberately conservative limit suits the initial single-guild rollout.
Two password hashing/verification operations can run concurrently to bound Argon2 memory.

### Membership administration API

All administrative endpoints require a current active Officer or Guild Master
bearer token. Promotion to Officer, demotion to Member, and passing Guild Master
additionally require the current active GM. Each mutation has a distinct route
and repository method, gated by `accounts.manage`.

| Endpoint | Request / result |
| --- | --- |
| `POST /api/auth/register` | Public JSON `username`, `display_name` (trimmed, 1–100 characters), `password` (12–128 characters); returns 201 with the pending Member account, without tokens/cookies |
| `GET /api/accounts` | Optional `membership_state`, `limit` (1–100, default 50), `offset` (default 0); returns `{accounts, limit, offset}` ordered by ID |
| `GET /api/accounts/{account_id}` | Returns public account fields only |
| `POST /api/accounts/{account_id}/approve` | Pending → active |
| `POST /api/accounts/{account_id}/reject` | Pending → rejected; then separately revokes every refresh-session family |
| `POST /api/accounts/{account_id}/deactivate` | Active → inactive; then separately revokes every refresh-session family |
| `POST /api/accounts/{account_id}/activate` | Rejected/inactive → active; fresh login required after successful session revocation |
| `POST /api/accounts/{account_id}/promote-to-officer` | GM only; Member → Officer |
| `POST /api/accounts/{account_id}/demote-to-member` | GM only; Officer → Member |
| `POST /api/accounts/{account_id}/pass-guild-master` | GM only; transfers to another active account; outgoing GM becomes Officer atomically |
| `GET /api/permissions` | Read-only `{permissions, roles}` catalog and fixed mappings |

Account results contain `id`, `username`, `display_name`, `membership_state`,
`role_name`, and `timezone`; credential hashes and session records are excluded.
Mutations return the resulting target account. Unknown accounts return 404,
invalid input 422, invalid state transitions/repeated actions/duplicate usernames
409, missing or invalid authentication 401, and insufficient authority 403.
Role changes take effect on existing bearer tokens at the next request. The old
generic role-update and GM-update PUT endpoints are not available.

Membership mutations and first-officer bootstrap share advisory transaction lock
730003 for operations that can reduce leadership: deactivation, demotion, and GM
succession. Succession locks affected accounts in ID order and rechecks GM
authority inside the same transaction as both updates. Other permission checks
are request-time API checks. Conditional writes reject conflicting target states;
the last active administrator cannot be deactivated or demoted, and a GM
cannot be deactivated or demoted outside transfer.

### First Guild Master and migration compatibility

The repo manager establishes the first GM directly in the database, promoting an
existing active account in a transaction. Coordinate this maintenance with account
administration and acquire `pg_advisory_xact_lock(730003)` before reading/updating
accounts. Verify no GM exists, update exactly the intended active account to
`role_name = 'guild_master'`, and verify the result before committing. No credentials
or actual member identifiers belong in repository examples or logs.

Zero GMs is allowed before this manual bootstrap. Migration 0003 enforces at most
one GM across all membership states, and API operations preserve one active GM
after bootstrap. Further succession uses the transfer endpoint; Officers cannot
change the GM. Direct database administration must preserve these invariants.

Migration 0003 preserves accounts and roles, drops the unused permission tables,
and fails transactionally with a clear error if multiple GM accounts exist. Resolve
duplicates manually before retrying; the migration never chooses an account.
Historical migrations remain unchanged.

Image rollback does not recreate dropped tables. Ticket 03 runtime authentication
does not query them, but its older migration checker rejects a ledger containing
0003, so readiness will remain unavailable on that image. Prefer a forward fix;
any rollback image must understand the migration ledger and avoid the removed
tables. Never delete ledger entries or reset member data to force compatibility.

### Interactive administrative CLI

Usernames are trimmed/lowercased and contain 3–32 ASCII letters, digits, or
underscores. New passwords contain 12–128 characters and are not trimmed. Passwords
use Argon2id. Both CLI commands prompt twice with hidden input and refuse an echoed
fallback when no terminal exists. Never supply a password in a command argument,
environment variable, shell history, or workflow input.

Locally, with migrations applied and the API container running:

```sh
docker compose exec api python -m bluddit_api.admin create-first-officer --username your_username --display-name 'Your name'
docker compose exec api python -m bluddit_api.admin reset-password --username your_username
```

For production, use verified SSH access and change into the resolved
`DEPLOY_PATH/current` release directory. Use an interactive terminal:

```sh
sudo docker compose --env-file release.env -f compose.production.yaml exec api python -m bluddit_api.admin create-first-officer --username your_username --display-name 'Your name'
sudo docker compose --env-file release.env -f compose.production.yaml exec api python -m bluddit_api.admin reset-password --username your_username
```

Do not add `-T`; hidden prompts need a terminal. These two account operations are
the approved exception to Actions-only production mutations. Bootstrap is serialized
and refuses to create another officer while an active Officer or Guild Master
exists. It never upgrades an existing account. Password reset leaves membership
and role unchanged and revokes every refresh session atomically with the update.
Commands report sanitized failures without passwords or database diagnostics.

Migration `0002_refresh_sessions.sql` adds refresh sessions and links access-token
records to them. It assumes the existing sessions table is empty, as agreed for
this ticket; it does not rewrite or revoke existing sessions. If that assumption
is false, the NOT NULL migration fails transactionally for review rather than
silently modifying records. Existing migration 0001 is unchanged. Rollback to the
previous health-only API image is compatible with the additive schema; rollback
does not undo schema or delete records.

### Client contract for ticket 05

Keep access tokens only in JavaScript memory and send them as bearer headers.
On reload or access expiry, refresh using the HttpOnly cookie. Share a single
in-flight refresh promise within a tab and coordinate refresh/logout across tabs
with a same-origin Web Lock. Broadcast new access tokens and logout events through
`BroadcastChannel`; never persist tokens in localStorage/sessionStorage. Use
`credentials: same-origin` for cookie operations and supply the origin/CSRF request
requirements above (browsers set Origin themselves). Retry a failed authenticated
request at most once after successful refresh. A stale refresh failure must not
clear a newer session; if another tab won the race, retry refresh once under the
shared lock with the current cookie. If that also fails, require login. Logout
must clear the tab's memory and notify other tabs even when its server request
fails, while making the server failure visible to the user.

## Account UI and shell (ticket 05)

The entry route `/` sends visitors to `/login` or authenticated members to `/home`.
Registration at `/register` creates a pending account and opens `/pending-approval`;
it does not create a session or expose membership status publicly. Officers use
`/admin/accounts`; Officers and GM can read `/admin/permissions`. GM-only role and
succession controls use the existing explicit account endpoints. Unbuilt member
features show temporary empty states. Password recovery remains the administrative
CLI workflow above.

The frontend uses local shadcn/ui primitives, Tailwind CSS, and a dark theme.
`apps/web/app/features/` groups screens, API contracts, and query options by feature.
`lib/http.ts` owns shared HTTP handling; `features/auth/session.ts` owns in-memory
tokens and coordinated refresh/logout. Feature `queries.ts` modules own query keys
and mutation invalidation. Routes are thin screen entry points; components do not
call fetch or duplicate API interfaces. Account writes invalidate account lists, the
affected detail, and session data without invalidating unrelated features. Temporary
background session errors preserve the mounted screen and show a retry notice;
confirmed session loss still clears access. See the
[web architecture README](../apps/web/README.md) for conventions and rationale.
Protected query keys include the acting account ID. Logout/session changes cancel
protected requests and remove cached member data. No query persistence is enabled;
credentials are read by mutation functions without entering mutation variables,
and access tokens remain solely in the session module's memory. Modern browsers
with Web Locks and BroadcastChannel over HTTPS (or localhost development) are
required. There are no new environment variables or database migrations.

For host development, `npm --prefix apps/web run dev` proxies `/api` to an API on
`127.0.0.1:8000`. Set the API's `AUTH_ALLOWED_ORIGINS` to the exact frontend origin,
for example `http://localhost:3000`. Compose continues to use its same-origin Nginx
proxy and existing allowed origins.

Install the browser once after `make setup`:

```sh
cd apps/web && npx playwright install chromium
```

Linux CI installs Chromium with `--with-deps`. `make web-test` runs Playwright;
`make verify` includes it. Set `TEST_DATABASE_URL` as described above to include
the real registration/approval/login test. Without it, the frontend-only test
command explicitly skips that integration test; full `make verify` still requires
the variable for database checks. The browser fixture requires a database name
ending in `_test`, creates a separate random database, applies current migrations,
seeds a synthetic GM, runs a test-only API on loopback port 18005, and drops the
isolated database on shutdown. It never seeds the member database. Playwright
reserves loopback port 4173 for its frontend. Synthetic fixture passwords are
public test data and must never be reused for real accounts.
