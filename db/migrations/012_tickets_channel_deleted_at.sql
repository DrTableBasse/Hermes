-- Migration 012 : marque les salons de tickets supprimés par le nettoyage à 48h
-- (channel_id est NOT NULL et sert à l'historique : on le conserve)
-- Exécuter manuellement : psql -U <user> -d <db> -f 012_tickets_channel_deleted_at.sql

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS channel_deleted_at TIMESTAMPTZ;
