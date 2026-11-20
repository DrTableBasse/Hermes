-- Migration 016 : galerie alimentée depuis #galerie (validation par ✅ du staff)
-- Exécuter manuellement : psql -U <user> -d <db> -f 016_gallery.sql

CREATE TABLE IF NOT EXISTS gallery_items (
    id            SERIAL PRIMARY KEY,
    message_id    BIGINT UNIQUE NOT NULL,
    channel_id    BIGINT,
    author_id     BIGINT NOT NULL,
    approved_by   BIGINT NOT NULL,
    kind          TEXT CHECK (kind IN ('image', 'clip')),
    file_name     TEXT,
    clip_url      TEXT,
    clip_provider TEXT,
    caption       TEXT,
    hidden        BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gallery_visible ON gallery_items (created_at DESC) WHERE hidden = FALSE;
