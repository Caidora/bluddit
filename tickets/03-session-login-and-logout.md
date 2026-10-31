# 03: Session login and logout

Status: Not started

Dependencies: Ticket 02.

## Outcome

Allow approved accounts to authenticate with server-managed sessions.

## Implementation

- Implement login, logout, and current-account endpoints, plus authenticated request dependencies.
- Use established password hashing and cryptographically random opaque session tokens. Store only token hashes in PostgreSQL.
- Set secure production cookie attributes, an explicit expiry, and session rotation on login. Revoke the session on logout.
- Protect state-changing requests against CSRF and reject disallowed origins. Add basic login throttling and generic login errors.
- Keep inactive or unapproved accounts out of member endpoints.
- Provide an administrative CLI for creating the first officer account and resetting a password, without logging secrets. No email service is required.

## Acceptance and verification

Correct credentials create a session; wrong credentials fail. Expired, revoked, inactive-account, and missing sessions fail. Cross-site mutation attempts fail. Logout invalidates the token at the server.

Implement meaningful checks for the behavior and failure paths above. Record commands run and results in the completion notes; do not claim external verification that has not happened.

## Completion notes

To be filled in by the implementing AI: changes, migrations/configuration, verification evidence, and any unresolved acceptance items.
