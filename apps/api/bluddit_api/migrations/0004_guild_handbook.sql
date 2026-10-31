-- Section URLs never change; all content lives in append-only revisions.
CREATE TABLE handbook_sections (
    slug text PRIMARY KEY CHECK (slug ~ '^[a-z][a-z0-9-]{0,79}$'),
    current_revision integer NOT NULL CHECK (current_revision > 0)
);

CREATE TABLE handbook_revisions (
    handbook_revision_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug text NOT NULL REFERENCES handbook_sections(slug),
    revision integer NOT NULL CHECK (revision > 0),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 160),
    body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 30000),
    updated_at timestamptz NOT NULL DEFAULT now(),
    author_account_id bigint NOT NULL REFERENCES accounts(id),
    UNIQUE (slug, revision)
);

ALTER TABLE handbook_sections ADD CONSTRAINT handbook_current_revision_fk
    FOREIGN KEY (slug, current_revision) REFERENCES handbook_revisions(slug, revision)
    DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION protect_handbook_revisions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Handbook revisions are immutable';
END;
$$;
CREATE TRIGGER handbook_revisions_immutable BEFORE UPDATE OR DELETE ON handbook_revisions
    FOR EACH ROW EXECUTE FUNCTION protect_handbook_revisions();
