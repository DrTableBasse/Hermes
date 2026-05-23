-- Migration 002: Extended Achievements — 28 nouveaux achievements
-- Date: 2026-05-19
-- Appliquer: psql -d saucisseland -f db/migrations/002_achievements_extended.sql

-- ─── Extensions user_voice_data (colonnes requises par les nouveaux achievements) ──
-- NOTE: nickname already exists in the base table; skipping it
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS longest_session_minutes INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS total_voice_sessions INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS unique_voice_channels_count INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS voice_night_minutes INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS voice_morning_minutes INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS consecutive_voice_days INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS max_streak_days INTEGER DEFAULT 0;
ALTER TABLE user_voice_data ADD COLUMN IF NOT EXISTS last_voice_date DATE;

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
