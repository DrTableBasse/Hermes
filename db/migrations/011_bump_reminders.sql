-- Migration 011 : rappels de bump en message privé
-- Exécuter manuellement : psql -U <user> -d <db> -f 011_bump_reminders.sql

-- Membres ayant demandé un rappel (/rappel-bump activer)
CREATE TABLE IF NOT EXISTS bump_reminder_subscribers (
    user_id     BIGINT PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- État global : un seul rang (id = 1), dernier bump détecté et rappel envoyé ou non
CREATE TABLE IF NOT EXISTS bump_reminder_state (
    id            SMALLINT PRIMARY KEY CHECK (id = 1),
    last_bump_at  TIMESTAMPTZ NOT NULL,
    reminded      BOOLEAN NOT NULL DEFAULT FALSE
);
