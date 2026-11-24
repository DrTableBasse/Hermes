-- Migration 023 : jeux en un clic et rôle de bump en règle (étape 4)
-- Idempotente et rejouable. La partie jeux est ajoutée plus bas par la tâche 2.

-- ── Rôle de bump : règle « bumps >= seuil » ────────────────────────────────
-- Seulement si bot_settings.bump_role est un identifiant numérique ; sinon (cas de la
-- production : valeur par défaut du registre) le bot crée la règle au démarrage.
WITH ins AS (
INSERT INTO role_rules (condition_type, condition_value, role_id)
SELECT 'bumps',
       COALESCE((SELECT v.value FROM bot_settings v
                 WHERE v.key = 'bump_role_threshold' AND v.value ~ '^[0-9]+$'), '20'),
       r.value::BIGINT
FROM bot_settings r
WHERE r.key = 'bump_role' AND r.value ~ '^[0-9]+$'
  AND NOT EXISTS (SELECT 1 FROM role_rules x WHERE x.condition_type = 'bumps')
  AND NOT EXISTS (SELECT 1 FROM bot_settings m WHERE m.key = 'bump_rule_seeded')
RETURNING id)
-- Marqueur : le bot n'amorce plus la règle (une suppression par un admin reste définitive).
INSERT INTO bot_settings (key, value)
SELECT 'bump_rule_seeded', '1' FROM ins
ON CONFLICT (key) DO NOTHING;
