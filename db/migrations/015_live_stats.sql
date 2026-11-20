-- Migration 015 : caserne en direct (relevés du serveur Discord + battement de cœur du bot)
-- Exécuter manuellement : psql -U <user> -d <db> -f 015_live_stats.sql

-- messages = nombre de messages depuis le relevé précédent
CREATE TABLE IF NOT EXISTS guild_stats_snapshots (
    taken_at  TIMESTAMPTZ PRIMARY KEY DEFAULT NOW(),
    members   INT NOT NULL,
    online    INT NOT NULL,
    in_voice  INT NOT NULL,
    messages  INT NOT NULL DEFAULT 0
);

-- Une ligne par minute où le bot est vivant
CREATE TABLE IF NOT EXISTS bot_heartbeats (
    minute TIMESTAMPTZ PRIMARY KEY
);
