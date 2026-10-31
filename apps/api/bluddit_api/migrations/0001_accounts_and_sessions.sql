CREATE TABLE accounts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text NOT NULL CHECK (btrim(username) <> '' AND username = btrim(username)),
    display_name text NOT NULL,
    password_hash text NOT NULL,
    membership_state text NOT NULL DEFAULT 'pending'
        CHECK (membership_state IN ('pending', 'active', 'rejected', 'inactive')),
    timezone text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX accounts_username_unique ON accounts (lower(username));

CREATE TABLE permission_grants (
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    capability text NOT NULL CHECK (capability IN ('organizer', 'quartermaster', 'officer')),
    PRIMARY KEY (account_id, capability)
);

CREATE TABLE sessions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL CHECK (expires_at > created_at),
    revoked_at timestamptz
);
CREATE INDEX sessions_account ON sessions(account_id);
CREATE INDEX sessions_expiry ON sessions(expires_at);
