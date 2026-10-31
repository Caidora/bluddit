# Bluddit

Bluddit.com is the member website for Bluds, replacing the guild’s shared planning spreadsheet. It supports efficient dungeon and raid progression, cooperation across AU/NZ/Perth, and a relaxed, positive guild culture.

## Project status

Ticket 01 is complete, as confirmed by the maintainer. Active work, recorded
acceptance status, and deployment evidence are tracked in
[GitHub issues](https://github.com/Caidora/bluddit/issues). The
[completed ticket reference](tickets/01-project-foundation.md) retains foundation
history. Release 1 is the current scope.

## Release 1

| Area | Functionality |
| --- | --- |
| Profiles and roster | Member-owned characters, professions, searchable roster, squads, and composition summaries |
| Gear and farming | Personal wishlists, acquisition updates, completion totals, and shared dungeon priorities |
| Events | Dated activities, local-time display, character/role signups, and organizer-managed rosters |
| Crafting directory | Crafters, profession and camp-buff coverage, material recipients, and delivery instructions |
| Guild handbook | Charter, leadership contacts, attendance expectations, loot policy, and operational rules |
| Member home page | Upcoming events, roster status, personal shortcuts, and useful farming priorities |

Members maintain their own information. Organizers manage assigned squads and events, quartermasters maintain material routing, and officers approve membership and maintain guild rules. Access uses username/password accounts with officer approval and server-side sessions. Common workflows must work on a phone.

## Plans and tickets

- [Contribution guide](contributions.md): required PR workflow, review, checks, and implementation practices. Never commit or push directly to `main`.
- [High-level plan](high-level-plan.md): guild purpose, source spreadsheet, and chosen stack.
- [Release-1 feature plan](website-feature-plan.md): member functionality, permissions, and completion criteria.
- [Implementation workflow and completed tickets](tickets/README.md): working rules, implementation defaults, and historical references.
- [GitHub issues](https://github.com/Caidora/bluddit/issues): active tickets, dependencies, progress, and acceptance evidence.
- [Ticket 01](tickets/01-project-foundation.md): application foundation, basic CI, and initial production deployment to Hetzner.

Complete migrated release-1 ticket sections in their original numerical order, one at a time, respecting the dependencies linked in GitHub issues. Record changes, verification evidence, deployed versions, and unresolved items in the corresponding issue. Close it as completed only after acceptance passes.

## Technology and repository layout

- React Router framework frontend using client-side rendering (CSR / SPA mode) in `apps/web`.
- FastAPI backend in `apps/api`.
- PostgreSQL with explicit parameterized SQL and numbered migrations; no ORM.
- Nginx and deployment configuration in `infra`.
- Docker containers and Docker Compose for local development and the server.
- GitHub Actions for CI and deployment.

The application includes health/readiness checks, authentication/membership APIs,
an account-recovery CLI, ticket 05 account screens, and an officer-authored guild
handbook with immutable revisions. The frontend uses shadcn/ui
and TanStack Query with shared HTTP/session handling and feature-owned typed API
modules. See the [web README](apps/web/README.md) for frontend architecture
conventions. The [permission matrix](docs/permissions.md) documents current gates
and resource checks required by later features.
The Python database driver is Psycopg 3, with a shared connection pool, explicit
SQL transactions, and numbered migrations. There is no ORM.

## Local development

With Docker and the Compose plugin (v2 or newer) installed:

```sh
cp .env.example .env
# Set POSTGRES_PASSWORD in .env.
make up
```

Open [the local website](http://localhost:8080). Use `make dev` for source reload,
`make down` to stop while preserving data, and `make logs` for local logs.
If port 8080 is occupied, set `LOCAL_PORT` in `.env`.

For host checks, install Node 24, Python 3.13, and uv 0.6.13, then run `make setup`
and install Chromium with `cd apps/web && npx playwright install chromium`.
Set `TEST_DATABASE_URL` to a disposable PostgreSQL database ending in `_test` before
running `make verify`; the test user needs permission to create disposable databases. Exact selected dependencies, configuration, and all development
and deployment commands are in the [operations runbook](docs/operations.md).

## CI and Hetzner deployment

Use the existing Hetzner server. Ticket 01 establishes production hosting, HTTPS, persistent database storage, health checks, and deployment through GitHub Actions.

Pull requests and `main` pushes run basic CI checks. Only `main` can publish images or run production operations, including manual workflow runs. Successful `main` builds deploy tested, versioned images to the server. Later tickets extend checks as features are added. Deployments run one at a time, with documented rollback and recovery procedures.

Each completed implementation ticket is deployed and verified in production using dedicated test records. Local and CI checks run before deployment. There is no separate staging environment planned.

### Repository-level secrets

Configure these as **GitHub Actions repository-level secrets**:

| Secret | Required value |
| --- | --- |
| `SSH_KEY` | The complete SSH private key used by the deployment workflow to connect to the Hetzner server, preserving its header, footer, and line breaks. The corresponding public key must be authorized for the deployment user on that server. |
| `SSH_KNOWN_HOSTS` | The contents of the SSH `known_hosts` file containing the verified host-key entry or entries for the Hetzner SSH hostname/IP and port used by the workflow. |
| `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PORT` | Confirmed Hetzner SSH address, account, and numeric port. |
| `DEPLOY_PATH` | Absolute application directory on the server. |
| `APP_DOMAIN` | Confirmed application hostname without a scheme or path. |
| `TLS_EMAIL` | Let's Encrypt certificate contact. |
| `POSTGRES_PASSWORD` | Production database password; no line breaks. |

The workflow must read these secrets into its SSH key and known-hosts configuration, restrict file permissions appropriately, and use host-key verification when connecting. Secret values must not be committed or printed in workflow logs.

These settings are secrets rather than Actions variables, matching the configured
repository. All production changes run through Actions. Use the main CI workflow for deployment,
rollback, restart, persistence verification, and backup. See the
[operations runbook](docs/operations.md) for server layout and recovery details.

## Spreadsheet transition

The source is the [Bludlets spreadsheet](https://docs.google.com/spreadsheets/d/1CtopiBvc1u_skUH29yOnmCAhc2qDYqVqrAiMTNWOgYE/edit). Import reviewed snapshots and confirm member-owned data before making it authoritative. The wishlist is labelled as a template, so its values require confirmation.

Keep planned characters and expected maximum levels separate from actual characters and current levels. Confirm server-specific game rules, precise member timezones, and the authoritative event schedule before importing those details.

After production verification and a member pilot, reconcile the final sheet changes, preserve a dated snapshot, and switch editing to the website. Core data exports and database backup/recovery are part of release 1.
