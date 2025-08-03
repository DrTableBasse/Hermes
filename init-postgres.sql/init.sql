-- Script d'initialisation PostgreSQL pour SaucisseLand
-- Création des utilisateurs et configuration des permissions

-- Créer l'utilisateur pour le site web
CREATE USER saucisseland_web WITH PASSWORD 'web_password_2024';

-- Créer l'utilisateur pour le bot Discord
CREATE USER hermes_bot WITH PASSWORD 'bot_password_2024';

-- Accorder les permissions sur la base de données
GRANT ALL PRIVILEGES ON DATABASE saucisseland TO saucisseland_web;
GRANT ALL PRIVILEGES ON DATABASE saucisseland TO hermes_bot;

-- Accorder les permissions sur le schéma public
GRANT ALL ON SCHEMA public TO saucisseland_web;
GRANT ALL ON SCHEMA public TO hermes_bot;

-- Accorder les permissions sur toutes les tables futures
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO saucisseland_web;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hermes_bot;

-- Accorder les permissions sur toutes les séquences futures
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO saucisseland_web;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hermes_bot;

-- Accorder les permissions sur toutes les fonctions futures
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO saucisseland_web;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO hermes_bot; 