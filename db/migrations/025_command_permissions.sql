-- Migration 025 : rôles autorisés par commande Hermes (étape 6)
-- Idempotente et rejouable.
CREATE TABLE IF NOT EXISTS command_permissions (
    command_name TEXT   NOT NULL,
    role_id      BIGINT NOT NULL,
    PRIMARY KEY (command_name, role_id)
);
