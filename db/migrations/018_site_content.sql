-- Migration 018 : contenus éditables depuis l'admin (jeux, pages)
-- Exécuter manuellement : psql -U <user> -d <db> -f 018_site_content.sql

CREATE TABLE IF NOT EXISTS site_games (
    key              TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    color            TEXT NOT NULL,
    image            TEXT,
    discord_role_id  BIGINT,
    forum_channel_id BIGINT,
    position         INT NOT NULL,
    active           BOOLEAN DEFAULT TRUE
);

-- Clés alignées sur GAMES de bot/cogs/fun/game_lfg.py ; War Dogs n'y figure pas.
INSERT INTO site_games (key, name, color, position) VALUES
    ('war-dogs',  'War Dogs',          '#A12D2F', 1),
    ('dbd',       'Dead by Daylight',  '#ED4245', 2),
    ('lol',       'League of Legends', '#F5A623', 3),
    ('warframe',  'Warframe',          '#5865F2', 4),
    ('overwatch', 'Overwatch',         '#FF9B50', 5),
    ('fortnite',  'Fortnite',          '#9B59B6', 6),
    ('minecraft', 'Minecraft',         '#57F287', 7)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS site_pages (
    slug       TEXT PRIMARY KEY,
    title      TEXT,
    body_md    TEXT,
    updated_by BIGINT,
    updated_at TIMESTAMPTZ
);

INSERT INTO site_pages (slug, title, body_md) VALUES
    ('reglement',        'Règlement',        ''),
    ('mentions-legales', 'Mentions légales', '')
ON CONFLICT (slug) DO NOTHING;
