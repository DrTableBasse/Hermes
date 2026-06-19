-- db/migrations/003_tickets.sql

CREATE TABLE tickets (
    id                 SERIAL PRIMARY KEY,
    user_id            BIGINT NOT NULL,
    title              TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'open',  -- open | resolved | closed
    discord_channel_id BIGINT,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    closed_at          TIMESTAMPTZ,
    created_by_admin   BOOLEAN DEFAULT FALSE
);

-- Enforce one open ticket per user at DB level
CREATE UNIQUE INDEX one_open_ticket_per_user
    ON tickets (user_id)
    WHERE (status = 'open');

CREATE TABLE ticket_messages (
    id          SERIAL PRIMARY KEY,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_id   BIGINT NOT NULL,
    author_name TEXT NOT NULL,
    content     TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'web',  -- 'web' | 'discord'
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON tickets(user_id);
CREATE INDEX ON tickets(status);
CREATE INDEX ON ticket_messages(ticket_id);
