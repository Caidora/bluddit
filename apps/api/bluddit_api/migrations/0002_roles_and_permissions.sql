-- Application validation owns these rules; retain uniqueness and foreign keys.
ALTER TABLE accounts DROP CONSTRAINT accounts_username_check;
ALTER TABLE accounts DROP CONSTRAINT accounts_membership_state_check;
ALTER TABLE sessions DROP CONSTRAINT sessions_token_hash_check;

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

-- One role per account; preserve any existing individual grants below.
ALTER TABLE accounts ADD COLUMN role_name text NOT NULL DEFAULT 'member' REFERENCES roles(name);

-- Preserve old capabilities as named permissions without inventing a role policy.
INSERT INTO permissions (name) SELECT DISTINCT capability FROM permission_grants;
ALTER TABLE permission_grants DROP CONSTRAINT permission_grants_capability_check;
ALTER TABLE permission_grants RENAME COLUMN capability TO permission_name;
ALTER TABLE permission_grants ADD FOREIGN KEY (permission_name) REFERENCES permissions(name) ON DELETE CASCADE;
