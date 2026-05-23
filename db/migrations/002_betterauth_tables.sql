-- BetterAuth session tables
-- Run manually: psql -U $PG_USER -d $PG_DB -f db/migrations/002_betterauth_tables.sql

CREATE TABLE IF NOT EXISTS "user" (
  "id"             TEXT PRIMARY KEY,
  "name"           TEXT NOT NULL,
  "email"          TEXT UNIQUE,
  "email_verified" BOOLEAN NOT NULL DEFAULT FALSE,
  "image"          TEXT,
  "created_at"     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updated_at"     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "discord_id"     TEXT UNIQUE,
  "is_admin"       BOOLEAN NOT NULL DEFAULT FALSE,
  "is_redacteur"   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS "session" (
  "id"          TEXT PRIMARY KEY,
  "expires_at"  TIMESTAMPTZ NOT NULL,
  "token"       TEXT NOT NULL UNIQUE,
  "created_at"  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updated_at"  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "ip_address"  TEXT,
  "user_agent"  TEXT,
  "user_id"     TEXT NOT NULL REFERENCES "user"("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "account" (
  "id"                       TEXT PRIMARY KEY,
  "account_id"               TEXT NOT NULL,
  "provider_id"              TEXT NOT NULL,
  "user_id"                  TEXT NOT NULL REFERENCES "user"("id") ON DELETE CASCADE,
  "access_token"             TEXT,
  "refresh_token"            TEXT,
  "id_token"                 TEXT,
  "access_token_expires_at"  TIMESTAMPTZ,
  "refresh_token_expires_at" TIMESTAMPTZ,
  "scope"                    TEXT,
  "password"                 TEXT,
  "created_at"               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "updated_at"               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "verification" (
  "id"         TEXT PRIMARY KEY,
  "identifier" TEXT NOT NULL,
  "value"      TEXT NOT NULL,
  "expires_at" TIMESTAMPTZ NOT NULL,
  "created_at" TIMESTAMPTZ DEFAULT NOW(),
  "updated_at" TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_token   ON "session"("token");
CREATE INDEX IF NOT EXISTS idx_session_user_id ON "session"("user_id");
CREATE INDEX IF NOT EXISTS idx_user_discord_id ON "user"("discord_id");
