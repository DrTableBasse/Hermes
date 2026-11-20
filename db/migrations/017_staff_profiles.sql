-- Migration 017 : profils éditables de l'état-major (phrase, jeux)
-- Exécuter manuellement : psql -U <user> -d <db> -f 017_staff_profiles.sql

CREATE TABLE IF NOT EXISTS staff_profiles (
    user_id    BIGINT PRIMARY KEY,
    motto      TEXT CHECK (char_length(motto) <= 140),
    games      TEXT[] DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
