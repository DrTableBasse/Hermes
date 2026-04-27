-- Migration: Ajouter la colonne nickname à user_voice_data
-- Date: 2025-11-23
-- Description: Ajoute la colonne nickname pour stocker le pseudo Discord sur le serveur

-- Ajouter la colonne nickname si elle n'existe pas
ALTER TABLE user_voice_data 
ADD COLUMN IF NOT EXISTS nickname VARCHAR(255);

-- Créer des index pour améliorer les performances de recherche
CREATE INDEX IF NOT EXISTS idx_user_voice_username 
ON user_voice_data(username);

CREATE INDEX IF NOT EXISTS idx_user_voice_nickname 
ON user_voice_data(nickname);

-- Commentaire pour documenter la colonne
COMMENT ON COLUMN user_voice_data.nickname IS 'Pseudo Discord sur le serveur (nickname). NULL si identique au username.';

