-- Migration 013 : réglages du serveur modifiables depuis l'admin du site
-- Exécuter manuellement : psql -U <user> -d <db> -f 013_settings.sql

CREATE TABLE IF NOT EXISTS bot_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_by  BIGINT,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
