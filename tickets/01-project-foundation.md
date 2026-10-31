# 01: Project foundation, CI, and Hetzner deployment

Status: In progress — local foundation implemented; CI and production acceptance pending

Dependencies: None.

## Outcome

Create a runnable application skeleton, basic CI, and a working production deployment on the existing Hetzner server. Subsequent tickets are deployed and tested there as they are completed.

## Implementation

- Create `apps/web` for the React Router framework CSR application (SPA mode), `apps/api` for FastAPI, and `infra` for deployment configuration.
- Add dependency manifests, lockfiles, environment examples, and root development instructions. Select supported versions at implementation time and record them.
- Add an API health endpoint, a basic web route, and PostgreSQL service configuration.
- Add a local Compose setup and a documented command for each common development action.
- Add GitHub Actions on pull requests and pushes to the repository's default branch: install from lockfiles, run web type checks and a production build, and run API tests including a health-endpoint test. Use the same documented commands locally and in CI.
- Add production web/API container builds, versioned images, PostgreSQL persistence, and Nginx routing for one public origin.
- Inspect the existing Hetzner setup and reuse the configured host, deployment access, and domain settings. Preserve unrelated services and data; document the application directory, ports, volumes, and deployment user.
- Configure HTTPS for the confirmed application domain, environment-supplied secrets, private database access, and health checks. Until authentication exists, expose only the skeleton page and non-sensitive health endpoints.
- Add a GitHub Actions deployment job for successful default-branch builds, using configured credentials and an explicit Hetzner target. Serialize deployments, deploy the tested image versions, check application health, and report failures.
- Deploy the skeleton to the actual Hetzner server and verify it through its public HTTPS URL. Test container restarts and deployment of a second version through the workflow.
- Document redeployment, logs, image rollback, and a database backup command. As migrations arrive in ticket 02, run them once per deployment and back up existing data before schema changes; reverting an image must not be treated as reverting a schema.
- Keep credentials out of source control.

## Acceptance and verification

A fresh checkout can start web, API, and PostgreSQL using the documented steps. The web page loads and the API health check responds. Missing required configuration produces an actionable error.

GitHub Actions passes for the initial application, and a successful default-branch build deploys to the existing Hetzner server. The public HTTPS page and health endpoint work, persistent data survives container restarts, and redeployment and image rollback are verified. Record the deployed commit/image and URL. If required host access, DNS, or GitHub secrets are unavailable, identify the missing setup and leave deployment acceptance pending rather than marking the ticket complete.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

Implemented React Router framework CSR web skeleton (SPA mode), FastAPI process health, locked
dependencies, production Dockerfiles, local/reload Compose, private PostgreSQL,
and same-origin Nginx routing. Selected Psycopg 3 for ticket 02; no migrations yet.

Added GitHub Actions verification, immutable GHCR image publication/testing,
serialized SSH deployment, HTTPS host setup, explicit rollback/restart/verify/backup
operations, and sanitized read-only preflight. Deployment settings are repository
secrets, matching their actual configuration. See `docs/operations.md`.

Local evidence so far: web type checks and production build passed; six API tests
passed; nine deployment failure-path tests passed; base/development Compose config
validation passed; production containers built and local web/API smoke passed at
port 18081 (8080 was already occupied). Docker Desktop was started for verification.

CSR update: disabled runtime server rendering with React Router SPA mode. The
production web image now serves only `build/client` using non-root Nginx on port
3000, with frontend route fallback and missing-asset 404s. Removed the React Router
runtime server dependency and updated rendering guidance across the plans/runbook.
Web type checks passed locally; the production Docker build passed type checks
and SPA generation. The host build hit sandbox restrictions on the temporary
Vite preview listener; the same build passed inside Docker. All 16 infrastructure
tests passed. An isolated production-style Compose stack passed the updated web/API
smoke check (loading shell, JS/CSS assets, nested route fallback, missing-asset 404,
and API health), then its disposable containers and volume were removed. The web
container also passed UID 1000 verification. Browser JavaScript execution and
production deployment of this change have not been verified.

Hetzner readiness workflow run 41170139868 passed after DEPLOY_PATH was corrected.
It reported Docker/Compose setup required, HTTP/HTTPS ports available, application
directory creation required, DNS resolving, and host setup permissions available.
This readiness check does not establish a successful deployment or DNS target match.

Pending: full GitHub CI, exact published-image checks, actual HTTPS deployment,
second-version deployment, production restart/persistence and backup/restore checks,
and image rollback. Record final workflow links, release manifests, and deployed
version once externally verified; do not mark Complete before these pass.
