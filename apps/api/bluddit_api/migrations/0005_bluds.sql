CREATE TABLE bluds (
    blud_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES accounts(id),
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 100),
    class_id text NOT NULL,
    spec_id text,
    character_created_on date NOT NULL,
    farming_zone_id text,
    farming_zone_updated_at timestamptz,
    archived boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by_account_id bigint NOT NULL REFERENCES accounts(id)
);
CREATE INDEX bluds_account ON bluds(account_id);
CREATE INDEX bluds_directory ON bluds(archived, lower(name), blud_id);

CREATE TABLE blud_professions (
    blud_id bigint NOT NULL REFERENCES bluds(blud_id),
    profession_id text NOT NULL,
    level integer CHECK (level >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (blud_id, profession_id)
);
CREATE INDEX blud_professions_filter ON blud_professions(profession_id, blud_id);

CREATE TABLE blud_dungeons (
    blud_id bigint NOT NULL REFERENCES bluds(blud_id),
    dungeon_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('not_completed', 'completed', 'completed_rerun')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (blud_id, dungeon_id)
);

-- A common read projection keeps directory and detail responses consistent.
CREATE VIEW blud_records AS
SELECT b.*, a.display_name AS owner_name,
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'profession_id', p.profession_id, 'level', p.level, 'updated_at', p.updated_at
    ) ORDER BY p.profession_id) FROM blud_professions p WHERE p.blud_id = b.blud_id), '[]'::jsonb) AS professions,
    COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'dungeon_id', d.dungeon_id, 'status', d.status, 'updated_at', d.updated_at
    ) ORDER BY d.dungeon_id) FROM blud_dungeons d WHERE d.blud_id = b.blud_id), '[]'::jsonb) AS dungeons
FROM bluds b JOIN accounts a ON a.id = b.account_id;
