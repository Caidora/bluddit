# 19: Production operational checks

Status: Not started

Dependencies: Ticket 18.

## Outcome

Verify the production deployment established in ticket 01 against the completed release-1 application.

## Implementation

- Review the existing Compose, Nginx, TLS, production session settings, trusted proxy behavior, and secrets configuration with the full member application. Ensure private responses are not publicly cached.
- Confirm CI includes web type/build checks, API tests against PostgreSQL, migration checks, and the key completed browser workflows; close gaps in the existing pipeline.
- Verify serialized deployment of versioned images, migration execution, health checks, failure reporting, persistent volumes, and documented rollback/recovery.
- Exercise deployed member workflows on the actual Hetzner production instance using dedicated test accounts and records. Clean up test records without changing member data.
- Verify the backup setup from ticket 18 and update the server/deployment runbook to match the live installation.

## Acceptance and verification

The completed application works on the existing Hetzner production instance, CI passes against real PostgreSQL, and deployment health/failure reporting and recovery procedures are verified. Record the deployed commit/image and production test results. No separate staging environment is required.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.
