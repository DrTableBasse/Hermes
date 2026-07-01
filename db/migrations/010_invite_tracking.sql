-- Migration 010 : suivi détaillé des invitations
-- Exécuter manuellement : psql -U <user> -d <db> -f 010_invite_tracking.sql

-- Codes d'invitation connus du bot
CREATE TABLE IF NOT EXISTS invite_codes (
    code        TEXT PRIMARY KEY,
    inviter_id  BIGINT NOT NULL,
    uses        INTEGER NOT NULL DEFAULT 0,
    max_uses    INTEGER,
    expires_at  TIMESTAMPTZ,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invite_codes_inviter ON invite_codes(inviter_id);
CREATE INDEX IF NOT EXISTS idx_invite_codes_active  ON invite_codes(is_active);

-- Historique des utilisations (un rang par membre ayant rejoint via une invitation)
CREATE TABLE IF NOT EXISTS invite_uses (
    id          BIGSERIAL PRIMARY KEY,
    invite_code TEXT     NOT NULL,
    inviter_id  BIGINT   NOT NULL,
    invitee_id  BIGINT   NOT NULL,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invite_uses_code    ON invite_uses(invite_code);
CREATE INDEX IF NOT EXISTS idx_invite_uses_inviter ON invite_uses(inviter_id);
CREATE INDEX IF NOT EXISTS idx_invite_uses_invitee ON invite_uses(invitee_id);
CREATE INDEX IF NOT EXISTS idx_invite_uses_joined  ON invite_uses(joined_at);
