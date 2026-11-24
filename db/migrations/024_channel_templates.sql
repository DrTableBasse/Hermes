-- Migration 024 : mémorisation des modèles d'accès appliqués aux salons (étape 5)
-- Idempotente et rejouable.
CREATE TABLE IF NOT EXISTS channel_templates (
    channel_id BIGINT PRIMARY KEY,
    template   VARCHAR(20) NOT NULL,
    roles      BIGINT[] NOT NULL DEFAULT '{}',
    applied_by BIGINT,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);
