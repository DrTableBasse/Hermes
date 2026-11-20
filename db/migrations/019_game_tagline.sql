-- Migration 019 : accroche éditable des jeux (affichée sur l'accueil, 120 caractères au plus)
-- Exécuter manuellement : psql -U <user> -d <db> -f 019_game_tagline.sql

ALTER TABLE site_games ADD COLUMN IF NOT EXISTS tagline TEXT;
