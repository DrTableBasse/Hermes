-- Migration 007: Fix achievements — 2026-06-21
-- 1. Supprime achievements non vérifiables ou inaccessibles aux utilisateurs normaux
-- 2. Attribue rétroactivement Citoyen Exemplaire + Champion de Discipline aux utilisateurs qualifiés

BEGIN;

-- Supprimer les user_achievements orphelins d'abord (FK)
DELETE FROM user_achievements
WHERE achievement_id IN (
    SELECT id FROM achievements
    WHERE condition_type IN (
        'articles_published', 'articles_written',  -- les utilisateurs normaux ne peuvent pas publier
        'warns_cleared',                            -- impossible à vérifier de façon fiable
        'messages_per_day',                         -- jamais tracké
        'mention_count',                            -- jamais tracké
        'login_count'                               -- jamais tracké
    )
);

DELETE FROM achievements
WHERE condition_type IN (
    'articles_published', 'articles_written',
    'warns_cleared',
    'messages_per_day',
    'mention_count',
    'login_count'
);

-- Attribuer rétroactivement warn_free (Sans reproche) aux utilisateurs sans avertissement
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'warn_free' AND a.condition_value = 0
WHERE NOT EXISTS (SELECT 1 FROM warn w WHERE w.user_id = u.user_id)
ON CONFLICT DO NOTHING;

-- Attribuer rétroactivement Citoyen Exemplaire + Champion de Discipline
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'warn_free_days'
WHERE EXTRACT(DAY FROM NOW() - COALESCE(
    (SELECT TO_TIMESTAMP(MAX(create_time)) FROM warn w WHERE w.user_id = u.user_id),
    u.created_at
))::int >= a.condition_value
ON CONFLICT DO NOTHING;

COMMIT;

SELECT
    (SELECT COUNT(*) FROM achievements)                                             AS total_achievements_restants,
    (SELECT COUNT(*) FROM user_achievements
     WHERE unlocked_at >= NOW() - INTERVAL '5 seconds')                            AS nouvellement_attribues;
