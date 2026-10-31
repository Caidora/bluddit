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

The Python PostgreSQL driver decision is **Psycopg 3**, using explicit parameterized
SQL and no ORM. Ticket 02 adds the dependency, pooling, readiness, and migrations.
There are no application migrations or authentication features in ticket 01.

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
port. API docs are disabled; the public API exposes only process health.

For source reload, use `make dev`. To run checks on the host, install Node 24,
Python 3.13, uv 0.6.13, and Make, then `make setup` and `make verify`.
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
| API / deployment tests | `make api-test` / `make infra-test` |
| Validate Compose configuration | `make config` |
| All host checks | `make verify` |

The local volume is `bluddit-local_postgres_data`. Never use `down --volumes` on
data you want to keep. Changing `POSTGRES_PASSWORD` after initialization does not
rotate the existing PostgreSQL account password.

## GitHub configuration

All production writes happen through **CI and production deployment** in Actions.
Pull requests and `main` pushes run the same host checks as local development and
smoke-test production containers. Successful `main` builds publish multi-platform
GHCR images, smoke-test their exact digests, and then deploy those digests.
Push-triggered runs are restricted to `main`; feature branches run CI through pull
requests. Image publication, production operations, and Hetzner preflight require
`main`, including manual workflow runs. Select `main` when dispatching preflight.

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

Before first deployment, run **Hetzner preflight**. It reports readiness only.
Confirm DNS A/AAAA records reach this server and public TCP 80/443 are permitted
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
compatibility requires review, even when the major version is unchanged. Once
ticket 02 introduces migrations, run them exactly once before application rollout,
back up existing data before schema changes, and assess schema compatibility
before selecting an older application image. Image rollback never undoes schema.

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
Actions, keeping workflow and release evidence together.
