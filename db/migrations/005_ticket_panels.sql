-- db/migrations/005_ticket_panels.sql
-- Remplace le système tickets web par le système Discord-only (wizard /ticket setup)

DROP TABLE IF EXISTS ticket_messages CASCADE;
DROP INDEX IF EXISTS one_open_ticket_per_user;
DROP TABLE IF EXISTS tickets CASCADE;

CREATE TABLE ticket_panels (
    id                    SERIAL PRIMARY KEY,
    guild_id              BIGINT NOT NULL,
    channel_id            BIGINT,
    message_id            BIGINT,
    category_id           BIGINT NOT NULL,
    log_channel_id        BIGINT,
    transcript_channel_id BIGINT,
    title                 TEXT NOT NULL DEFAULT 'Support',
    description           TEXT NOT NULL DEFAULT '',
    color                 INTEGER NOT NULL DEFAULT 5793266,
    footer                TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ticket_types (
    id                      SERIAL PRIMARY KEY,
    panel_id                INTEGER NOT NULL REFERENCES ticket_panels(id) ON DELETE CASCADE,
    guild_id                BIGINT NOT NULL,
    label                   TEXT NOT NULL,
    emoji                   TEXT NOT NULL DEFAULT '📝',
    description             TEXT NOT NULL DEFAULT '',
    welcome_message         TEXT NOT NULL,
    notification_channel_id BIGINT,
    field1_label            TEXT,
    field1_required         BOOLEAN NOT NULL DEFAULT TRUE,
    field2_label            TEXT,
    field2_required         BOOLEAN NOT NULL DEFAULT FALSE,
    field3_label            TEXT,
    field3_required         BOOLEAN NOT NULL DEFAULT FALSE,
    field4_label            TEXT,
    field4_required         BOOLEAN NOT NULL DEFAULT FALSE,
    field5_label            TEXT,
    field5_required         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE tickets (
    id            SERIAL PRIMARY KEY,
    guild_id      BIGINT NOT NULL,
    channel_id    BIGINT NOT NULL,
    user_id       BIGINT NOT NULL,
    ticket_number INTEGER NOT NULL,
    panel_id      INTEGER REFERENCES ticket_panels(id),
    type_id       INTEGER REFERENCES ticket_types(id),
    subject       TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'open',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON tickets(guild_id, status);
CREATE INDEX ON tickets(channel_id);
