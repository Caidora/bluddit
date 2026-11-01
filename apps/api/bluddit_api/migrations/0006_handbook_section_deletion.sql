-- Only deleting a whole section may remove its immutable revisions.
ALTER TABLE handbook_revisions DROP CONSTRAINT handbook_revisions_slug_fkey;
ALTER TABLE handbook_revisions ADD CONSTRAINT handbook_revisions_slug_fkey
    FOREIGN KEY (slug) REFERENCES handbook_sections(slug) ON DELETE CASCADE;

CREATE OR REPLACE FUNCTION protect_handbook_revisions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND NOT EXISTS (
        SELECT 1 FROM handbook_sections WHERE slug = OLD.slug
    ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'Handbook revisions are immutable';
END;
$$;
