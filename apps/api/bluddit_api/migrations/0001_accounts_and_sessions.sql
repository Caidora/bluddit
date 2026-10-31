CREATE TABLE roles (
    name text PRIMARY KEY
);
INSERT INTO roles (name) VALUES ('member'), ('organizer'), ('quartermaster'), ('officer');

CREATE TABLE permissions (
    name text PRIMARY KEY
);

CREATE TABLE role_permissions (
    role_name text NOT NULL REFERENCES roles(name) ON DELETE CASCADE,
    permission_name text NOT NULL REFERENCES permissions(name) ON DELETE CASCADE,
    PRIMARY KEY (role_name, permission_name)
);

CREATE TABLE accounts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text NOT NULL,
    display_name text NOT NULL,
    password_hash text NOT NULL,
    membership_state text NOT NULL DEFAULT 'pending',
    role_name text NOT NULL DEFAULT 'member' REFERENCES roles(name),
    timezone text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX accounts_username_unique ON accounts (lower(username));

CREATE TABLE permission_grants (
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    permission_name text NOT NULL REFERENCES permissions(name) ON DELETE CASCADE,
    PRIMARY KEY (account_id, permission_name)
);

CREATE TABLE sessions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token_hash bytea NOT NULL UNIQUE,
    account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL CHECK (expires_at > created_at),
    revoked_at timestamptz
);
CREATE INDEX sessions_account ON sessions(account_id);
CREATE INDEX sessions_expiry ON sessions(expires_at);
