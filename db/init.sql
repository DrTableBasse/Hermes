-- Hermes v2 — Database Schema
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Core user table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_voice_data (
    user_id       BIGINT PRIMARY KEY,
    username      VARCHAR(255) NOT NULL,
    nickname      VARCHAR(255),
    discord_avatar VARCHAR(500),
    total_time    INTEGER DEFAULT 0,
    is_member     BOOLEAN NOT NULL DEFAULT TRUE,
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
    id               SERIAL PRIMARY KEY,
    command_name     VARCHAR(100) NOT NULL,
    guild_id         BIGINT,
    is_enabled       BOOLEAN DEFAULT TRUE,
    disabled_by_name VARCHAR(255),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
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

-- ─── Extensions user_voice_data ──────────────────────────────
-- NOTE: nickname already exists in the base table above
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

-- ─── Quest templates (pool de quêtes disponibles) ───────────
CREATE TABLE IF NOT EXISTS quest_templates (
    id           SERIAL PRIMARY KEY,
    title        VARCHAR(255) NOT NULL,
    description  TEXT,
    quest_type   VARCHAR(50) NOT NULL,
    target_value INTEGER NOT NULL,
    xp_reward    INTEGER DEFAULT 50,
    icon         VARCHAR(10) DEFAULT '📋',
    is_enabled   BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quest_templates_type ON quest_templates(quest_type, is_enabled);

INSERT INTO quest_templates (title, description, quest_type, target_value, xp_reward, icon) VALUES
-- Messages (12 quêtes)
('Prise de parole',       'Envoyer 10 messages cette semaine',    'messages', 10,   10,  '🗣️'),
('Bavard débutant',       'Envoyer 30 messages cette semaine',    'messages', 30,   20,  '💬'),
('Actif du jour',         'Envoyer 50 messages cette semaine',    'messages', 50,   25,  '💬'),
('Causeur',               'Envoyer 75 messages cette semaine',    'messages', 75,   35,  '💬'),
('Grand bavard',          'Envoyer 150 messages cette semaine',   'messages', 150,  55,  '💬'),
('Super actif',           'Envoyer 200 messages cette semaine',   'messages', 200,  60,  '📢'),
('Moulin à paroles',      'Envoyer 300 messages cette semaine',   'messages', 300,  80,  '📢'),
('Hyper actif',           'Envoyer 400 messages cette semaine',   'messages', 400,  90,  '📢'),
('Incontournable',        'Envoyer 500 messages cette semaine',   'messages', 500,  100, '📢'),
('Verbeux',               'Envoyer 600 messages cette semaine',   'messages', 600,  115, '📢'),
('Champion du chat',      'Envoyer 750 messages cette semaine',   'messages', 750,  130, '🏆'),
('Légende du chat',       'Envoyer 1000 messages cette semaine',  'messages', 1000, 160, '👑'),
-- Vocal (12 quêtes)
('Premier pas vocal',     'Passer 10 minutes en vocal',           'voice_minutes', 10,  10,  '🎤'),
('Vocal régulier',        'Passer 30 minutes en vocal',           'voice_minutes', 30,  20,  '🎤'),
('Présence vocale',       'Passer 45 minutes en vocal',           'voice_minutes', 45,  25,  '🎤'),
('Voix d''or',            'Passer 1h en vocal',                   'voice_minutes', 60,  35,  '🎤'),
('Bavard vocal',          'Passer 1h30 en vocal',                 'voice_minutes', 90,  45,  '🎤'),
('Accro au vocal',        'Passer 2h en vocal',                   'voice_minutes', 120, 55,  '🎙️'),
('Vocaliste',             'Passer 3h en vocal',                   'voice_minutes', 180, 70,  '🎙️'),
('Voix du serveur',       'Passer 4h en vocal',                   'voice_minutes', 240, 80,  '🎙️'),
('Marathonien vocal',     'Passer 5h en vocal',                   'voice_minutes', 300, 90,  '🎙️'),
('Vocal assidu',          'Passer 6h en vocal',                   'voice_minutes', 360, 100, '📻'),
('Vocal de nuit',         'Passer 8h en vocal',                   'voice_minutes', 480, 120, '📻'),
('Vocal intense',         'Passer 10h en vocal',                  'voice_minutes', 600, 150, '📻'),
-- Bumps (8 quêtes)
('Premier bump',          'Bumper le serveur 1 fois',             'bumps', 1,  15,  '📣'),
('Bumper régulier',       'Bumper le serveur 3 fois',             'bumps', 3,  30,  '📣'),
('Supporter',             'Bumper le serveur 5 fois',             'bumps', 5,  50,  '📣'),
('Bumper de la semaine',  'Bumper le serveur 7 fois',             'bumps', 7,  65,  '📣'),
('Boosteur',              'Bumper le serveur 10 fois',            'bumps', 10, 80,  '📈'),
('Ambassadeur',           'Bumper le serveur 15 fois',            'bumps', 15, 100, '📈'),
('Super bumper',          'Bumper le serveur 20 fois',            'bumps', 20, 120, '📈'),
('Bump addict',           'Bumper le serveur 30 fois',            'bumps', 30, 150, '📈'),
-- Invitations (4 quêtes)
('Recruteur débutant',    'Inviter 1 personne sur le serveur',    'invites', 1, 30,  '🤝'),
('Recruteur',             'Inviter 2 personnes sur le serveur',   'invites', 2, 60,  '🤝'),
('Ambassadeur du serveur','Inviter 3 personnes sur le serveur',   'invites', 3, 100, '🤝'),
('Recruteur de l''année', 'Inviter 5 personnes sur le serveur',   'invites', 5, 150, '🏆'),
-- Images postées (7 quêtes)
('Photographe',           'Poster 1 image ou vidéo',              'images_posted', 1,  10,  '📸'),
('Galerie',               'Poster 3 images ou vidéos',            'images_posted', 3,  25,  '📸'),
('Partage visuel',        'Poster 5 images ou vidéos',            'images_posted', 5,  40,  '🖼️'),
('Artiste visuel',        'Poster 8 images ou vidéos',            'images_posted', 8,  55,  '🖼️'),
('Photographe fou',       'Poster 10 images ou vidéos',           'images_posted', 10, 65,  '🖼️'),
('Peintre numérique',     'Poster 15 images ou vidéos',           'images_posted', 15, 90,  '🎨'),
('Maître de la galerie',  'Poster 25 images ou vidéos',           'images_posted', 25, 130, '🎨'),
-- Réactions données (7 quêtes)
('Réactif',               'Donner 5 réactions à des messages',    'reactions_given', 5,   15,  '👍'),
('Expressif',             'Donner 15 réactions à des messages',   'reactions_given', 15,  30,  '😄'),
('Super réactif',         'Donner 20 réactions à des messages',   'reactions_given', 20,  40,  '😄'),
('Émotionnel',            'Donner 30 réactions à des messages',   'reactions_given', 30,  50,  '😄'),
('Réacteur pro',          'Donner 50 réactions à des messages',   'reactions_given', 50,  75,  '❤️'),
('Émoji master',          'Donner 75 réactions à des messages',   'reactions_given', 75,  95,  '❤️'),
('Roi des émojis',        'Donner 100 réactions à des messages',  'reactions_given', 100, 120, '🎭')
ON CONFLICT DO NOTHING;

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

-- ─── 28 Nouveaux achievements ─────────────────────────────────
INSERT INTO achievements (name, description, icon, condition_type, condition_value, points) VALUES
-- Vocaux (7)
('Nocturne',               'Passer 60 min en vocal de nuit (22h-6h)',          '🌙', 'voice_night_minutes',    60,    15),
('Matinal',                'Passer 60 min en vocal le matin (6h-9h)',          '🌅', 'voice_morning_minutes',  60,    15),
('Sociale',                'Rester en vocal plus de 2h en une session',        '👥', 'longest_session_minutes',120,   20),
('Marathonien',            'Rester en vocal plus de 8h en une session',        '🏃', 'longest_session_minutes',480,   50),
('Présence Constante',     'Passer du vocal 10 jours consécutifs',             '📅', 'consecutive_voice_days', 10,    35),
('Pack des Vocaux',        'Être dans un vocal avec 3+ membres simultanément', '🎙️', 'max_concurrent_members', 3,     25),
('Voyageur des Canaux',    'Se connecter à 5 canaux vocaux différents',        '🧳', 'unique_voice_channels',  5,     20),
-- Messages (6)
('Spammer Responsable',    'Envoyer des messages dans 10+ canaux distincts',   '📢', 'messages_multi_channel', 10,    25),
('Streak Verbal',          'Envoyer au moins 1 message 7 jours consécutifs',   '🔥', 'message_streak_days',    7,     25),
('Marathonien du Chat',    'Envoyer 100 messages en une journée',              '⚡', 'messages_per_day',       100,   20),
('Influenceur',            'Être mentionné dans 10 messages différents',       '⭐', 'mention_count',          10,    20),
-- Communauté (6)
('Bumpeur Obsédé',         'Effectuer 50 bumps du serveur',                    '📈', 'bumps',                  50,    40),
('Bumpeur Légendaire',     'Effectuer 100 bumps du serveur',                   '🚀', 'bumps',                  100,   75),
('Connecté Web',           'Se connecter une première fois sur la plateforme', '🌐', 'login_count',            1,     10),
('Habitué Web',            'Se connecter 10 fois sur la plateforme',           '💻', 'login_count',            10,    25),
('Ancien du Serveur',      'Être membre depuis 6 mois',                        '🏛️', 'days_on_server',         180,   50),
('Légende du Serveur',     'Être membre depuis 1 an',                          '👑', 'days_on_server',         365,   100),
-- Articles (3)
('Première Plume',         'Publier son premier article',                      '✍️', 'articles_published',     1,     20),
('Auteur Prolifique',      'Publier 5 articles',                               '📚', 'articles_published',     5,     50),
('Scribe du Serveur',      'Publier 10 articles',                              '📖', 'articles_published',     10,    100),
-- Modération (3)
('Citoyen Exemplaire',     'Passer 90 jours sans avertissement',               '✨', 'warn_free_days',         90,    30),
('Champion de Discipline', 'Passer 180 jours sans avertissement',              '🛡️', 'warn_free_days',         180,   60),
('Rédemption',             'Avoir tous ses avertissements supprimés',          '🌟', 'warns_cleared',          1,     40),
-- Easter Eggs (3)
('Passionné Anime',        'Utiliser /blague 25 fois',                        '🎌', 'blague_count',           25,    15),
('Blagueur du Serveur',    'Utiliser /blague 50 fois',                        '😂', 'blague_count',           50,    15),
('Confesseur Secret',      'Utiliser /confess 5 fois',                        '🤐', 'confess_count',          5,     20)
ON CONFLICT DO NOTHING;

-- ─── Bump stats ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_bump_stats (
    user_id     BIGINT PRIMARY KEY REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    bump_count  INTEGER DEFAULT 0,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bump_stats_count ON user_bump_stats(bump_count DESC);

-- ─── Invite stats ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_invite_stats (
    user_id       BIGINT PRIMARY KEY REFERENCES user_voice_data(user_id) ON DELETE CASCADE,
    invite_count  INTEGER DEFAULT 0,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invite_stats_count ON user_invite_stats(invite_count DESC);

-- ─── Achievements de niveau ──────────────────────────────────────
INSERT INTO achievements (name, description, icon, condition_type, condition_value, points) VALUES
    ('Apprenti',    'Atteindre le niveau 5',   '🌱', 'level', 5,   20),
    ('Initié',      'Atteindre le niveau 10',  '⚡', 'level', 10,  40),
    ('Confirmé',    'Atteindre le niveau 20',  '🔥', 'level', 20,  75),
    ('Expert',      'Atteindre le niveau 50',  '💎', 'level', 50,  100),
    ('Légende XP',  'Atteindre le niveau 100', '👑', 'level', 100, 150)
ON CONFLICT DO NOTHING;

-- ─── Achievements invitations ────────────────────────────────────
INSERT INTO achievements (name, description, icon, condition_type, condition_value, points) VALUES
    ('Ambassadeur',          'Inviter 1 membre sur le serveur',   '🤝', 'invites', 1,   15),
    ('Recruteur',            'Inviter 5 membres sur le serveur',  '📨', 'invites', 5,   35),
    ('Roi des Invitations',  'Inviter 25 membres sur le serveur', '👑', 'invites', 25,  75)
ON CONFLICT DO NOTHING;

-- ─── BetterAuth tables (camelCase — required by better-auth v1.x) ──────────
CREATE TABLE IF NOT EXISTS "user" (
  "id"           TEXT PRIMARY KEY,
  "name"         TEXT NOT NULL,
  "email"        TEXT UNIQUE,
  "emailVerified" BOOLEAN NOT NULL DEFAULT FALSE,
  "image"        TEXT,
  "createdAt"    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updatedAt"    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "discordId"    TEXT UNIQUE,
  "isAdmin"      BOOLEAN NOT NULL DEFAULT FALSE,
  "isRedacteur"  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS "session" (
  "id"         TEXT PRIMARY KEY,
  "expiresAt"  TIMESTAMPTZ NOT NULL,
  "token"      TEXT NOT NULL UNIQUE,
  "createdAt"  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updatedAt"  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "ipAddress"  TEXT,
  "userAgent"  TEXT,
  "userId"     TEXT NOT NULL REFERENCES "user"("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "account" (
  "id"                    TEXT PRIMARY KEY,
  "accountId"             TEXT NOT NULL,
  "providerId"            TEXT NOT NULL,
  "userId"                TEXT NOT NULL REFERENCES "user"("id") ON DELETE CASCADE,
  "accessToken"           TEXT,
  "refreshToken"          TEXT,
  "idToken"               TEXT,
  "accessTokenExpiresAt"  TIMESTAMPTZ,
  "refreshTokenExpiresAt" TIMESTAMPTZ,
  "scope"                 TEXT,
  "password"              TEXT,
  "createdAt"             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updatedAt"             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "verification" (
  "id"         TEXT PRIMARY KEY,
  "identifier" TEXT NOT NULL,
  "value"      TEXT NOT NULL,
  "expiresAt"  TIMESTAMPTZ NOT NULL,
  "createdAt"  TIMESTAMPTZ DEFAULT NOW(),
  "updatedAt"  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_token   ON "session"("token");
CREATE INDEX IF NOT EXISTS idx_session_user_id ON "session"("userId");
CREATE INDEX IF NOT EXISTS idx_user_discord_id ON "user"("discordId");

-- ─── Admin action logs ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admin_logs (
    id           SERIAL PRIMARY KEY,
    action_type  VARCHAR(50) NOT NULL,
    actor_id     BIGINT,
    actor_name   VARCHAR(255),
    target_id    BIGINT,
    target_name  VARCHAR(255),
    details      JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_admin_logs_created ON admin_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_logs_type    ON admin_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_admin_logs_actor   ON admin_logs(actor_id);
