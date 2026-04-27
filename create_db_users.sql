-- Script pour créer les utilisateurs PostgreSQL manuellement
-- À exécuter si le script d'initialisation Docker n'a pas fonctionné

-- Se connecter en tant que postgres superuser
-- psql -U postgres -d saucisseland -f create_db_users.sql

-- Créer l'utilisateur pour le site web
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'saucisseland_web') THEN
        CREATE USER saucisseland_web WITH PASSWORD 'web_password_2024';
    END IF;
END
$$;

-- Créer l'utilisateur pour le bot Discord
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'hermes_bot') THEN
        CREATE USER hermes_bot WITH PASSWORD 'bot_password_2024';
    END IF;
END
$$;

-- Accorder les permissions sur la base de données
GRANT ALL PRIVILEGES ON DATABASE saucisseland TO saucisseland_web;
GRANT ALL PRIVILEGES ON DATABASE saucisseland TO hermes_bot;

-- Accorder les permissions sur le schéma public
GRANT ALL ON SCHEMA public TO saucisseland_web;
GRANT ALL ON SCHEMA public TO hermes_bot;

-- Accorder les permissions sur toutes les tables existantes
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO saucisseland_web;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hermes_bot;

-- Accorder les permissions sur toutes les séquences existantes
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO saucisseland_web;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO hermes_bot;

-- Accorder les permissions sur toutes les tables futures
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO saucisseland_web;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hermes_bot;

-- Accorder les permissions sur toutes les séquences futures
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO saucisseland_web;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hermes_bot;

-- Accorder les permissions sur toutes les fonctions futures
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO saucisseland_web;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO hermes_bot;

