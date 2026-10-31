CREATE TABLE refresh_sessions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    token_hash bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL CHECK (expires_at > created_at),
    revoked_at timestamptz
);
CREATE INDEX refresh_sessions_account ON refresh_sessions(account_id);
CREATE INDEX refresh_sessions_expiry ON refresh_sessions(expires_at);

ALTER TABLE sessions ADD COLUMN refresh_session_id bigint NOT NULL
    REFERENCES refresh_sessions(id) ON DELETE CASCADE;
CREATE INDEX sessions_refresh_session ON sessions(refresh_session_id);
