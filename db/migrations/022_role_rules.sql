-- Migration 022 : règles de rôles automatiques (étape 3)
-- Idempotente et rejouable.

CREATE TABLE IF NOT EXISTS role_rules (
    id                SERIAL PRIMARY KEY,
    condition_type    VARCHAR(20) NOT NULL,
    condition_value   TEXT        NOT NULL,
    role_id           BIGINT,
    create_role_name  VARCHAR(100),
    create_role_color INT,
    remove_when_lost  BOOLEAN     NOT NULL DEFAULT FALSE,
    exclusive_group   VARCHAR(50),
    active            BOOLEAN     NOT NULL DEFAULT TRUE,
    reconcile         BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by        BIGINT,
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    CHECK (role_id IS NOT NULL
           OR (condition_type = 'achievement' AND create_role_name IS NOT NULL))
);

-- Ancien rôle visé, mémorisé quand un PATCH change role_id : seul rôle que
-- « appliquer » accepte de retirer à ses porteurs (remove_previous_role_id).
ALTER TABLE role_rules ADD COLUMN IF NOT EXISTS previous_role_id BIGINT;

-- Batman : heures de vocal >= voice_hours_for_role (100 par défaut).
INSERT INTO role_rules (condition_type, condition_value, role_id)
SELECT 'voice_hours',
       COALESCE((SELECT v.value FROM bot_settings v
                 WHERE v.key = 'voice_hours_for_role' AND v.value ~ '^[0-9]+$'), '100'),
       r.value::BIGINT
FROM bot_settings r
WHERE r.key = 'role_batman' AND r.value ~ '^[0-9]+$'
  AND NOT EXISTS (SELECT 1 FROM role_rules x
                  WHERE x.condition_type = 'voice_hours' AND x.role_id = r.value::BIGINT);

-- Rôles de niveau : seulement ceux réglés et numériques.
INSERT INTO role_rules (condition_type, condition_value, role_id)
SELECT 'level', substring(s.key FROM 12), s.value::BIGINT
FROM bot_settings s
WHERE s.key IN ('role_level_5', 'role_level_10', 'role_level_20', 'role_level_50')
  AND s.value ~ '^[0-9]+$'
  AND NOT EXISTS (SELECT 1 FROM role_rules x
                  WHERE x.condition_type = 'level' AND x.role_id = s.value::BIGINT);

-- Succès : « créer au premier déblocage », couleur selon le palier
-- (mêmes seuils et couleurs que achievements_notifier._tier).
INSERT INTO role_rules (condition_type, condition_value, create_role_name, create_role_color)
SELECT 'achievement', a.id::TEXT,
       COALESCE(NULLIF(a.icon, ''), '🏆') || ' ' || a.name,
       CASE WHEN a.points >= 100 THEN 16098851   -- Légendaire (or)
            WHEN a.points >= 50  THEN 5793266    -- Épique (bleu)
            WHEN a.points >= 25  THEN 16751440   -- Rare (orange)
            ELSE 9807270 END                     -- Commun (gris)
FROM achievements a
WHERE NOT EXISTS (SELECT 1 FROM role_rules x
                  WHERE x.condition_type = 'achievement' AND x.condition_value = a.id::TEXT);
