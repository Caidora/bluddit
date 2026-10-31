# Bluddit

Bluddit.com is the member website for Bluds, replacing the guild’s shared planning spreadsheet. It supports efficient dungeon and raid progression, cooperation across AU/NZ/Perth, and a relaxed, positive guild culture.

## Project status

The initial planning documentation and 20 implementation tickets are in place. Application implementation has not started. Release 1 is the current scope.

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

- [High-level plan](high-level-plan.md): guild purpose, source spreadsheet, and chosen stack.
- [Release-1 feature plan](website-feature-plan.md): member functionality, permissions, and completion criteria.
- [Implementation ticket index](tickets/README.md): ordered tickets, dependencies, implementation defaults, and working rules.
- [Ticket 01](tickets/01-project-foundation.md): application foundation, basic CI, and initial production deployment to Hetzner.

Complete tickets in numerical order, one at a time. Each ticket specifies implementation work and acceptance checks. The implementing AI records changes, verification evidence, deployed version, and unresolved items in the ticket before updating its status.

## Technology and repository layout

- React Router framework frontend in `apps/web`.
- FastAPI backend in `apps/api`.
- PostgreSQL with explicit parameterized SQL and numbered migrations; no ORM.
- Nginx and deployment configuration in `infra`.
- Docker containers and Docker Compose for local development and the server.
- GitHub Actions for CI and deployment.

These application directories will be created in ticket 01. Dependency versions and development commands will be documented during implementation. The high-level plan’s `ngpsql` wording needs resolving when selecting the Python backend’s PostgreSQL driver.

## CI and Hetzner deployment

Use the existing Hetzner server. Ticket 01 establishes production hosting, HTTPS, persistent database storage, health checks, and deployment through GitHub Actions.

Pull requests and default-branch pushes run basic CI checks. Successful default-branch builds deploy tested, versioned images to the server. Later tickets extend checks as features are added. Deployments run one at a time, with documented rollback and recovery procedures.

Each completed implementation ticket is deployed and verified in production using dedicated test records. Local and CI checks run before deployment. There is no separate staging environment planned.

### Repository-level secrets

Configure these as **GitHub Actions repository-level secrets**:

| Secret | Required value |
| --- | --- |
| `SSH_KEY` | The complete SSH private key used by the deployment workflow to connect to the Hetzner server, preserving its header, footer, and line breaks. The corresponding public key must be authorized for the deployment user on that server. |
| `SSH_KNOWN_HOSTS` | The contents of the SSH `known_hosts` file containing the verified host-key entry or entries for the Hetzner SSH hostname/IP and port used by the workflow. |

The workflow must read these secrets into its SSH key and known-hosts configuration, restrict file permissions appropriately, and use host-key verification when connecting. Secret values must not be committed or printed in workflow logs.

The server address, SSH user/port, application directory, domain/DNS, and any other required deployment configuration must be confirmed from the existing setup during ticket 01. The two secrets provide the authentication key and trusted host identities; they do not establish those connection settings by themselves.

## Spreadsheet transition

The source is the [Bludlets spreadsheet](https://docs.google.com/spreadsheets/d/1CtopiBvc1u_skUH29yOnmCAhc2qDYqVqrAiMTNWOgYE/edit). Import reviewed snapshots and confirm member-owned data before making it authoritative. The wishlist is labelled as a template, so its values require confirmation.

Keep planned characters and expected maximum levels separate from actual characters and current levels. Confirm server-specific game rules, precise member timezones, and the authoritative event schedule before importing those details.

After production verification and a member pilot, reconcile the final sheet changes, preserve a dated snapshot, and switch editing to the website. Core data exports and database backup/recovery are part of release 1.
