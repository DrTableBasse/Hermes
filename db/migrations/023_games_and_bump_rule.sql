-- Migration 023 : jeux en un clic et rôle de bump en règle (étape 4)
-- Idempotente et rejouable. La partie jeux est ajoutée plus bas par la tâche 2.

-- ── Rôle de bump : règle « bumps >= seuil » ────────────────────────────────
-- Seulement si bot_settings.bump_role est un identifiant numérique ; sinon (cas de la
-- production : valeur par défaut du registre) le bot crée la règle au démarrage.
INSERT INTO role_rules (condition_type, condition_value, role_id)
SELECT 'bumps',
       COALESCE((SELECT v.value FROM bot_settings v
                 WHERE v.key = 'bump_role_threshold' AND v.value ~ '^[0-9]+$'), '20'),
       r.value::BIGINT
FROM bot_settings r
WHERE r.key = 'bump_role' AND r.value ~ '^[0-9]+$'
  AND NOT EXISTS (SELECT 1 FROM role_rules x WHERE x.condition_type = 'bumps');
