-- Migration 001: Gamification — XP, streaks, quests, notifications, endorsements, comments, automod
-- Date: 2026-05-19
-- Appliquer: psql -d saucisseland -f db/migrations/001_gamification.sql

-- ─── Extensions user_voice_data ──────────────────────────────
-- NOTE: nickname already exists in the base table; skipping it
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS longest_session_minutes INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS total_voice_sessions INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS unique_voice_channels_count INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS voice_night_minutes INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS voice_morning_minutes INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS consecutive_voice_days INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS max_streak_days INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS last_voice_date DATE;

-- ─── XP et niveaux ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_xp (
    user_id       BIGINT PRIMARY KEY REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    total_xp      INTEGER DEFAULT 0,
    current_level INTEGER DEFAULT 1,
    weekly_xp     INTEGER DEFAULT 0,
    monthly_xp    INTEGER DEFAULT 0,
    week_start    DATE DEFAULT CURRENT_DATE,
    month_start   DATE DEFAULT DATE_TRUNC('month', CURRENT_DATE)::DATE,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_xp_level  ON user_xp(current_level DESC);
CREATE INDEX IF NOT EXISTS idx_user_xp_weekly ON user_xp(weekly_xp DESC);

-- ─── Streaks vocaux ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_streaks (
    user_id          BIGINT PRIMARY KEY REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    current_streak   INTEGER DEFAULT 0,
    max_streak       INTEGER DEFAULT 0,
    last_active_date DATE,
    streak_type      VARCHAR(20) DEFAULT 'voice',
    xp_multiplier    NUMERIC(3,2) DEFAULT 1.00,
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Streaks messages ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_message_streaks (
    user_id           BIGINT PRIMARY KEY REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    current_streak    INTEGER DEFAULT 0,
    max_streak        INTEGER DEFAULT 0,
    last_message_date DATE,
    messages_today    INTEGER DEFAULT 0,
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Weekly Quests ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weekly_quests (
    id           SERIAL PRIMARY KEY,
    title        VARCHAR(255) NOT NULL,
    description  TEXT,
    quest_type   VARCHAR(50) NOT NULL,  -- 'messages' | 'voice_minutes' | 'bumps' | 'articles'
    target_value INTEGER NOT NULL,
    xp_reward    INTEGER DEFAULT 50,
    icon         VARCHAR(10) DEFAULT '📋',
    week_start   DATE NOT NULL,
    week_end     DATE NOT NULL,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_weekly_quests_active ON weekly_quests(is_active, week_start);

CREATE TABLE IF NOT EXISTS user_quest_progress (
    user_id        BIGINT   NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    quest_id       INTEGER  NOT NULL REFERENCES weekly_quests(id) ON DELETE CASCADE,
    progress_value INTEGER DEFAULT 0,
    completed      BOOLEAN DEFAULT FALSE,
    completed_at   TIMESTAMPTZ,
    xp_claimed     BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (user_id, quest_id)
);
CREATE INDEX IF NOT EXISTS idx_quest_progress_user ON user_quest_progress(user_id);

-- ─── Notifications ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_notifications (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    type        VARCHAR(50) NOT NULL,  -- 'achievement' | 'level_up' | 'quest_complete' | 'endorsement' | 'article_comment'
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    related_id  INTEGER,
    read        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON user_notifications(user_id, read);
CREATE INDEX IF NOT EXISTS idx_notifications_created     ON user_notifications(created_at DESC);

-- ─── Endorsements ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS endorsements (
    id           SERIAL PRIMARY KEY,
    from_user_id BIGINT NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    to_user_id   BIGINT NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    category     VARCHAR(20) NOT NULL CHECK (category IN ('helpful','funny','creative','inclusive')),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_user_id, to_user_id, category)
);
CREATE INDEX IF NOT EXISTS idx_endorsements_to   ON endorsements(to_user_id);
CREATE INDEX IF NOT EXISTS idx_endorsements_from ON endorsements(from_user_id);

CREATE TABLE IF NOT EXISTS user_reputation (
    user_id         BIGINT PRIMARY KEY REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    helpful_count   INTEGER DEFAULT 0,
    funny_count     INTEGER DEFAULT 0,
    creative_count  INTEGER DEFAULT 0,
    inclusive_count INTEGER DEFAULT 0,
    total_count     INTEGER GENERATED ALWAYS AS (helpful_count + funny_count + creative_count + inclusive_count) STORED,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Leaderboard snapshots ────────────────────────────────────
CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    id           SERIAL PRIMARY KEY,
    period_type  VARCHAR(10) NOT NULL CHECK (period_type IN ('weekly','monthly')),
    period_start DATE NOT NULL,
    user_id      BIGINT NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    metric_type  VARCHAR(20) NOT NULL CHECK (metric_type IN ('messages','voice','xp')),
    metric_value BIGINT DEFAULT 0,
    rank         INTEGER,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(period_type, period_start, user_id, metric_type)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_period ON leaderboard_snapshots(period_type, period_start, metric_type);

-- ─── Article comments ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS article_comments (
    id                SERIAL PRIMARY KEY,
    article_id        INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    user_id           BIGINT  NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    parent_comment_id INTEGER REFERENCES article_comments(id) ON DELETE CASCADE,
    content           TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 2000),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comments_article ON article_comments(article_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comments_parent  ON article_comments(parent_comment_id);

CREATE TABLE IF NOT EXISTS article_votes (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    user_id    BIGINT  NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    vote_type  SMALLINT NOT NULL CHECK (vote_type IN (1, -1)),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (article_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_article_votes_article ON article_votes(article_id);

-- ─── Extension articles ───────────────────────────────────────
ALTER TABLE articles ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0;

-- ─── Auto-modération ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS automod_config (
    guild_id            BIGINT PRIMARY KEY,
    enabled             BOOLEAN DEFAULT TRUE,
    blocked_words       TEXT[] DEFAULT '{}',
    max_mentions        INTEGER DEFAULT 10,
    spam_threshold      INTEGER DEFAULT 3,
    spam_window_seconds INTEGER DEFAULT 5,
    log_channel_id      BIGINT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS automod_logs (
    id         SERIAL PRIMARY KEY,
    guild_id   BIGINT NOT NULL,
    user_id    BIGINT NOT NULL,
    action     VARCHAR(50) NOT NULL,
    reason     TEXT,
    channel_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_automod_logs_guild ON automod_logs(guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_automod_logs_user  ON automod_logs(user_id);

-- ─── Statistiques de commandes (easter eggs) ─────────────────
CREATE TABLE IF NOT EXISTS user_command_stats (
    user_id      BIGINT NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    command_name VARCHAR(100) NOT NULL,
    usage_count  INTEGER DEFAULT 0,
    last_used    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, command_name)
);
CREATE INDEX IF NOT EXISTS idx_cmd_stats_user ON user_command_stats(user_id);

-- ─── Tracking canaux vocaux uniques ──────────────────────────
CREATE TABLE IF NOT EXISTS user_voice_channels (
    user_id     BIGINT NOT NULL REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    channel_id  BIGINT NOT NULL,
    total_time  INTEGER DEFAULT 0,
    visit_count INTEGER DEFAULT 1,
    first_visit TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, channel_id)
);
CREATE INDEX IF NOT EXISTS idx_voice_channels_user ON user_voice_channels(user_id);
