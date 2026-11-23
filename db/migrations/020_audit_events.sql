-- Migration 020 : journal unique des évènements (étape 1 « Journal et Modération »)
-- Idempotente. admin_logs n'est pas supprimée.

CREATE TABLE IF NOT EXISTS audit_events (
    id            BIGSERIAL PRIMARY KEY,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kind          VARCHAR(32)  NOT NULL,
    action        VARCHAR(100) NOT NULL,
    source        VARCHAR(16)  NOT NULL CHECK (source IN ('site', 'hermes', 'discord')),
    actor_id      BIGINT,
    actor_name    VARCHAR(255),
    target_id     BIGINT,
    target_name   VARCHAR(255),
    channel_id    BIGINT,
    channel_name  VARCHAR(255),
    success       BOOLEAN NOT NULL DEFAULT TRUE,
    details       JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_events_occurred ON audit_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_kind     ON audit_events(kind, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor    ON audit_events(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_target   ON audit_events(target_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_action   ON audit_events(action);

-- Reprise de l'historique d'admin_logs (une seule fois : table encore vide).
INSERT INTO audit_events
    (occurred_at, kind, action, source, actor_id, actor_name, target_id, target_name, details)
SELECT created_at,
       CASE
           WHEN action_type IN ('kick', 'ban', 'timeout', 'warn', 'delete_warn') THEN 'sanction'
           WHEN action_type LIKE 'quest\_%' THEN 'content'
           ELSE 'setting'
       END,
       action_type, 'site', actor_id, actor_name, target_id, target_name,
       COALESCE(details, '{}'::jsonb)
FROM admin_logs
WHERE NOT EXISTS (SELECT 1 FROM audit_events)
ORDER BY created_at;
