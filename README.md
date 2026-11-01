# Bluddit

[Bluddit.com](https://bluddit.com) is the member website for Bluds: a place to manage WoW Forever characters, organize runs, share gear goals, and find guild knowledge. It supports cooperation across AU/NZ/Perth and a relaxed, positive guild culture, with a playful, Reddit-inspired personality.

The [Bludlets spreadsheet](https://docs.google.com/spreadsheets/d/1CtopiBvc1u_skUH29yOnmCAhc2qDYqVqrAiMTNWOgYE/edit) is a reference for the guild’s needs and ideas. Bluddit is its own product: the website’s workflows and data model should develop around members’ needs, without having to reproduce the sheet’s tabs, formulas, or feature set.

## Project status

As of 1 November 2026, Release 1 is in development.

- **Available:** the application foundation and production deployment, database migrations, session login/logout, registration and membership approval, account administration, permissions, and the guild handbook with officer editing and revision history.
- **In review:** the Bluds directory, character details, professions, farming zones, and dungeon completion tracking. This work is not yet part of the current checkout or an accepted production release.
- **Planned:** events, personal gear wishlists, material routing and the crafter directory, a useful member home page, and expanded database snapshot/recovery support.

The full Release 1 experience is not complete. Some member pages are still placeholders; their presence in navigation does not mean the feature is available. Implementation, review, and production verification are separate steps.

## Release 1

| Area | Intended experience |
| --- | --- |
| Accounts and access | Username/password accounts, officer-approved membership, session-based access, and server-enforced permissions |
| Bluds | A searchable directory of members’ characters, with class/spec, professions and levels, farming zone, creation date, and dungeon progress including an interest in rerunning completed dungeons |
| Events | Member-created activities with a start time displayed in the viewer’s timezone, optional destination, group size and duration, plus signups and roster management; raid-specific support is deferred |
| Personal gear wishlist | Character-owned item goals, sources and notes, filtering, and needed/acquired updates with undo |
| Materials and crafters | Searchable recipients, crafters, specializations, outputs, and delivery instructions, with maintained routing rather than inventory accounting |
| Guild handbook | Officer-authored rules and useful guild knowledge, searchable member pages, and attributable revision history |
| Member home | Upcoming activities and signup status, personal shortcuts, and access to the completed guild tools |
| Data recovery | Database snapshots, documented restore procedures, retention, and off-host backup storage |

Members maintain their own characters, wishlists, and signups. Officers manage membership and guild knowledge; the Guild Master controls account-role changes and succession. Event management and other shared responsibilities need explicit permissions and resource checks. Common workflows must work comfortably on a phone.

Squads, composition dashboards, guild-wide farming rankings, camp-buff coverage, and spreadsheet import are not current Release 1 commitments. The [feature plan](website-feature-plan.md) describes scope and boundaries in more detail.

## Local development on macOS

### Prerequisites

For the container stack, install:

- **Git and Make**, available through Apple’s Command Line Tools (`xcode-select --install`).
- **Docker Desktop for Mac**, using the installer for your Apple silicon or Intel Mac. Start Docker Desktop and wait for its engine to be ready. Docker Compose v2 or newer is required.
- A modern browser supporting Web Locks and BroadcastChannel; use localhost for development.

To run checks or frontend/backend processes directly on your Mac, also install **Node 24** (npm included), **Python 3.13**, and **uv** (CI uses **0.6.13**). `.nvmrc` selects Node 24 if you use nvm. uv can install the required Python with `uv python install 3.13`. The containers supply their own Node, Python, and PostgreSQL, so these host runtimes are not needed just to run the website.

### Start the website

From a checkout of this repository:

```sh
cp .env.example .env
# Edit .env and choose a local POSTGRES_PASSWORD before continuing.
make dev
```

Open [localhost:8080](http://localhost:8080). `make dev` starts PostgreSQL, applies migrations, and runs the web/API stack with source reload. The first build downloads dependencies and images. Use `make up` for production-style local containers instead.

If port 8080 is in use, set `LOCAL_PORT` in `.env` and use that port in the browser. If Docker Desktop reports a denied bind mount, allow the checkout directory in its file-sharing settings. Source edits reload automatically; rerun `make dev` after dependency or container configuration changes.

A fresh database has no approved accounts. Create the first local officer interactively, then sign in and approve registered members:

```sh
docker compose exec api python -m bluddit_api.admin create-first-officer --username local_officer --display-name 'Local Officer'
```

The command prompts for a password and refuses a second bootstrap once an active Officer or GM exists. See the [runbook](docs/operations.md#interactive-administrative-cli) for password recovery and GM setup.

| Action | Command |
| --- | --- |
| Follow logs | `make logs` |
| Stop while preserving local data | `make down` |
| Inspect migrations | `make migration-status` |
| Apply migrations explicitly | `make migrate` |
| Validate Compose files | `make config` |

Local data lives in a Docker volume. Do not remove volumes to stop the stack; changing `.env` after initialization does not rotate the existing database password.

### Run checks on your Mac

With the host runtimes installed:

```sh
# If using nvm, run nvm use first.
make setup
(cd apps/web && npx playwright install chromium)
```

Full verification needs a **separate disposable PostgreSQL 17 database**, reachable from the host, with a database name ending in `_test` and a user allowed to create databases. The application database is deliberately not exposed on a host port. For example, start a dedicated local test container:

```sh
docker run --name bluddit-test-db -d \
  -e POSTGRES_USER=bluddit_test \
  -e POSTGRES_PASSWORD=local-test-password \
  -e POSTGRES_DB=bluddit_test \
  -p 127.0.0.1:25432:5432 postgres:17-bookworm

docker exec bluddit-test-db pg_isready -U bluddit_test -d bluddit_test
```

Wait until `pg_isready` reports that connections are accepted, then run:

```sh
export TEST_DATABASE_URL='postgresql://bluddit_test:local-test-password@127.0.0.1:25432/bluddit_test'
make verify
```

The export must be in the shell running the checks; placing it in `.env` alone does not export it to host tests. Fixtures create and remove their own random databases. `make verify` runs web types/build/browser checks, API and database tests, infrastructure tests, and Compose validation. For Python changes, run Ruff separately as described in the [contribution guide](contributions.md). Stop the test database with `docker stop bluddit-test-db` and reuse it later with `docker start bluddit-test-db`.

### Windows differences

Use **WSL2 with a Linux distribution** and Docker Desktop’s WSL integration for the closest match to these instructions. Keep the checkout in the WSL filesystem, enable integration for that distribution, and run commands in its shell. Install Git, Make, Node, Python, and uv inside WSL; Apple’s Command Line Tools and macOS version-manager setup do not apply. Playwright on Linux may need `npx playwright install --with-deps chromium` to install system dependencies.

Native PowerShell requires different environment-variable syntax (`$env:TEST_DATABASE_URL = '...'`) and line continuation, and does not supply Make or the POSIX shell expected by the Makefile. Use the WSL shell for the documented workflow.

## Technology and repository layout

| Location | Purpose |
| --- | --- |
| `apps/web` | React Router framework SPA with React, TypeScript, shadcn/ui, and TanStack Query |
| `apps/api` | FastAPI, Psycopg 3 connection pooling, explicit parameterized SQL, and numbered migrations; no ORM |
| `infra` | Nginx, container deployment tooling, and infrastructure checks |
| `docs` | Operations and permission documentation |

Docker Compose runs the stack locally and on the existing Hetzner server. GitHub Actions checks pull requests; successful `main` builds publish and deploy tested, versioned images. Deployments are serialized, and image rollback does not reverse database migrations. There is no separate staging environment; verify deployed features with dedicated test records while preserving member data.

## Documentation

- [Contribution guide](contributions.md): PR workflow, scope, implementation practices, and verification. All changes go through a PR; never commit or push directly to `main`.
- [Operations runbook](docs/operations.md): selected versions, configuration and secrets, deployment, migrations, backups, rollback, and account recovery.
- [Feature plan](website-feature-plan.md): Release 1 behavior and scope boundaries.
- [High-level plan](high-level-plan.md): guild purpose, product direction, and architecture.
- [Web architecture](apps/web/README.md): frontend organization, API calls, caching, and session handling.
- [Permission policy](docs/permissions.md): current access gates and resource authorization conventions.
