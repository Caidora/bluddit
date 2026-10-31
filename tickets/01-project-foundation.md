# 01: Project foundation, CI, and Hetzner deployment

Status: Not started

Dependencies: None.

## Outcome

Create a runnable application skeleton, basic CI, and a working production deployment on the existing Hetzner server. Subsequent tickets are deployed and tested there as they are completed.

## Implementation

- Create `apps/web` for the React Router framework application, `apps/api` for FastAPI, and `infra` for deployment configuration.
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

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.
