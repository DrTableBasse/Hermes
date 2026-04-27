-- Hermes v2 — Database Schema
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Core user table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_voice_data (
    user_id       BIGINT PRIMARY KEY,
    username      VARCHAR(255) NOT NULL,
    nickname      VARCHAR(255),
    discord_avatar VARCHAR(500),
    total_time    INTEGER DEFAULT 0,
    last_seen     TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_voice_username   ON user_voice_data(username);
CREATE INDEX IF NOT EXISTS idx_user_voice_total_time ON user_voice_data(total_time DESC);

-- ─── Warnings ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS warn (
    id           SERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES user_voice_data(user_id),
    reason       TEXT NOT NULL,
    create_time  BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_warn_user_id ON warn(user_id);

-- ─── Message stats ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_message_stats (
    user_id       BIGINT NOT NULL REFERENCES user_voice_data(user_id),
    channel_id    BIGINT NOT NULL,
    message_count INTEGER DEFAULT 1,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_msg_stats_user ON user_message_stats(user_id);

-- ─── Command enable/disable ───────────────────────────────────
CREATE TABLE IF NOT EXISTS command_status (
    id           SERIAL PRIMARY KEY,
    command_name VARCHAR(100) NOT NULL,
    guild_id     BIGINT,
    is_enabled   BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(command_name, guild_id)
);

CREATE INDEX IF NOT EXISTS idx_command_status_name_guild ON command_status(command_name, guild_id);

-- ─── OAuth2 sessions ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       BIGINT NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    access_token  TEXT NOT NULL,
    refresh_token TEXT,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);

-- ─── Articles ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS articles (
    id              SERIAL PRIMARY KEY,
    author_id       BIGINT NOT NULL REFERENCES user_voice_data(user_id),
    title           VARCHAR(500) NOT NULL,
    slug            VARCHAR(500) UNIQUE NOT NULL,
    content         TEXT NOT NULL,
    cover_image_url TEXT,
    published       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_slug      ON articles(slug);
CREATE INDEX IF NOT EXISTS idx_articles_author    ON articles(author_id);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published, created_at DESC);

-- ─── Tags ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tags (
    id    SERIAL PRIMARY KEY,
    name  VARCHAR(100) UNIQUE NOT NULL,
    slug  VARCHAR(100) UNIQUE NOT NULL,
    color VARCHAR(7) DEFAULT '#3b82f6'
);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

-- ─── Media uploads ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS media (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploaded_by   BIGINT REFERENCES user_voice_data(user_id),
    filename      TEXT NOT NULL,
    original_name TEXT NOT NULL,
    url           TEXT NOT NULL,
    size          INTEGER,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Achievements ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS achievements (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    icon            VARCHAR(10),
    condition_type  VARCHAR(50) NOT NULL,   -- 'messages' | 'voice_hours' | 'warn_free'
    condition_value INTEGER NOT NULL,
    points          INTEGER DEFAULT 10
);

CREATE TABLE IF NOT EXISTS user_achievements (
    user_id        BIGINT  NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    achievement_id INTEGER NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
    unlocked_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, achievement_id)
);

-- ─── Default achievements ─────────────────────────────────────
INSERT INTO achievements (name, description, icon, condition_type, condition_value, points) VALUES
    ('Premier message',   'Envoyer votre premier message',       '✉️', 'messages',    1,     10),
    ('Bavard',            'Envoyer 100 messages',                '💬', 'messages',    100,   25),
    ('Moulin à paroles',  'Envoyer 1 000 messages',              '🗣️', 'messages',    1000,  50),
    ('Légende du chat',   'Envoyer 10 000 messages',             '👑', 'messages',    10000, 100),
    ('Vocal débutant',    'Passer 1 heure en vocal',             '🎤', 'voice_hours', 1,     10),
    ('Vocal régulier',    'Passer 10 heures en vocal',           '🎙️', 'voice_hours', 10,    25),
    ('Vocal assidu',      'Passer 100 heures en vocal',          '📻', 'voice_hours', 100,   50),
    ('Voix du serveur',   'Passer 500 heures en vocal',          '🏆', 'voice_hours', 500,   100),
    ('Sans reproche',     'N''avoir aucun avertissement actif',  '✅', 'warn_free',   0,     20)
ON CONFLICT DO NOTHING;
