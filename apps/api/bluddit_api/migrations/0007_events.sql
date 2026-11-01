CREATE TABLE events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
    activity_type text NOT NULL CHECK (activity_type IN ('dungeon', 'leveling', 'questing', 'pvp', 'guild_meeting', 'other')),
    dungeon_id text,
    starts_at timestamptz NOT NULL,
    scheduling_timezone text NOT NULL CHECK (length(scheduling_timezone) BETWEEN 1 AND 100),
    duration_minutes integer CHECK (duration_minutes > 0),
    capacity integer CHECK (capacity > 0),
    requirements text NOT NULL DEFAULT '' CHECK (length(requirements) <= 10000),
    state text NOT NULL DEFAULT 'scheduled' CHECK (state IN ('scheduled', 'cancelled')),
    created_by_account_id bigint NOT NULL REFERENCES accounts(id),
    updated_by_account_id bigint NOT NULL REFERENCES accounts(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX events_schedule ON events(state, starts_at, event_id);
CREATE TABLE event_organizers (
    event_id bigint NOT NULL REFERENCES events(event_id),
    account_id bigint NOT NULL REFERENCES accounts(id),
    PRIMARY KEY (event_id, account_id)
);
CREATE INDEX event_organizers_account ON event_organizers(account_id, event_id);

CREATE VIEW event_records AS
SELECT e.event_id, e.title, e.activity_type, e.dungeon_id, e.starts_at,
       e.scheduling_timezone, e.duration_minutes, e.capacity, e.requirements,
       e.state, e.created_by_account_id, e.updated_by_account_id,
       e.created_at, e.updated_at,
       COALESCE((SELECT jsonb_agg(jsonb_build_object(
           'account_id', a.id, 'display_name', a.display_name,
           'active', a.membership_state = 'active') ORDER BY a.display_name, a.id)
           FROM event_organizers o JOIN accounts a ON a.id = o.account_id
           WHERE o.event_id = e.event_id), '[]'::jsonb) AS organizers
FROM events e;
