-- Migration 021 : accès partiels à l'admin (étape 2)
-- Idempotente.

CREATE TABLE IF NOT EXISTS site_permissions (
    discord_role_id BIGINT      NOT NULL,
    permission      VARCHAR(50) NOT NULL,
    granted_by      BIGINT,
    granted_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (discord_role_id, permission)
);

ALTER TABLE "user"
    ADD COLUMN IF NOT EXISTS "sitePermissions" TEXT[] NOT NULL DEFAULT '{}';

-- Comportement actuel préservé : le rôle rédacteur garde ses droits d'articles.
INSERT INTO site_permissions (discord_role_id, permission)
SELECT s.value::BIGINT, p.permission
FROM bot_settings s
CROSS JOIN (VALUES ('articles.write'), ('articles.publish')) AS p(permission)
WHERE s.key = 'redacteur_role' AND s.value ~ '^[0-9]+$'
ON CONFLICT DO NOTHING;
