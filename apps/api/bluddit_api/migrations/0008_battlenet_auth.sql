-- Preserve local credentials until each legacy account is explicitly linked.
ALTER TABLE accounts ALTER COLUMN username DROP NOT NULL;
ALTER TABLE accounts ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE accounts
    ADD COLUMN battle_net_account_id bigint UNIQUE CHECK (battle_net_account_id > 0),
    ADD COLUMN battletag text,
    ADD COLUMN battle_net_access_token bytea,
    ADD COLUMN battle_net_token_obtained_at timestamptz,
    ADD COLUMN battle_net_token_expires_at timestamptz,
    ADD CONSTRAINT accounts_auth_identity CHECK (
        (battle_net_account_id IS NULL AND username IS NOT NULL AND password_hash IS NOT NULL
            AND battletag IS NULL AND battle_net_access_token IS NULL
            AND battle_net_token_obtained_at IS NULL AND battle_net_token_expires_at IS NULL)
        OR (battle_net_account_id IS NOT NULL AND password_hash IS NULL
            AND battletag IS NOT NULL AND battle_net_access_token IS NOT NULL
            AND battle_net_token_obtained_at IS NOT NULL AND battle_net_token_expires_at IS NOT NULL
            AND battle_net_token_expires_at > battle_net_token_obtained_at)
    );

CREATE TABLE oauth_attempts (
    oauth_attempt_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state_hash bytea NOT NULL UNIQUE,
    browser_hash bytea NOT NULL,
    return_to text NOT NULL,
    account_id bigint REFERENCES accounts(id) ON DELETE CASCADE,
    credential_version bytea,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '10 minutes',
    consumed_at timestamptz,
    CHECK ((account_id IS NULL) = (credential_version IS NULL))
);
CREATE INDEX oauth_attempts_expiry ON oauth_attempts(expires_at);
CREATE TABLE oauth_registrations (
    oauth_registration_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token_hash bytea NOT NULL UNIQUE,
    battle_net_account_id bigint NOT NULL CHECK (battle_net_account_id > 0),
    battletag text NOT NULL,
    access_token bytea NOT NULL,
    obtained_at timestamptz NOT NULL,
    token_expires_at timestamptz NOT NULL CHECK (token_expires_at > obtained_at),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '10 minutes',
    consumed_at timestamptz
);
CREATE INDEX oauth_registrations_expiry ON oauth_registrations(expires_at);
-- Immediate migration requirement: no pre-OAuth sessions survive rollout.
UPDATE refresh_sessions SET revoked_at = now() WHERE revoked_at IS NULL;
UPDATE sessions SET revoked_at = now() WHERE revoked_at IS NULL;
