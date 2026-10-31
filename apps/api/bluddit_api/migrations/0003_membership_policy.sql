-- Permission policy now lives in Python; account roles retain their foreign key.
DROP TABLE role_permissions;
DROP TABLE permissions;

DO $$
BEGIN
    IF (SELECT count(*) FROM accounts WHERE role_name = 'guild_master') > 1 THEN
        RAISE EXCEPTION 'Multiple Guild Masters exist; resolve manually before migration';
    END IF;
END $$;

CREATE UNIQUE INDEX accounts_single_guild_master ON accounts (role_name)
    WHERE role_name = 'guild_master';
