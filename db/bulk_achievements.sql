BEGIN;

-- 1. messages
INSERT INTO user_achievements (user_id, achievement_id)
SELECT ms.user_id, a.id
FROM (SELECT user_id, COALESCE(SUM(message_count),0) AS total FROM user_message_stats GROUP BY user_id) ms
JOIN achievements a ON a.condition_type = 'messages' AND ms.total >= a.condition_value
ON CONFLICT DO NOTHING;

-- 2. voice_hours
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'voice_hours' AND u.total_time::float/3600 >= a.condition_value
ON CONFLICT DO NOTHING;

-- 3. warn_free
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'warn_free' AND a.condition_value = 0
WHERE NOT EXISTS (SELECT 1 FROM warn w WHERE w.user_id = u.user_id)
ON CONFLICT DO NOTHING;

-- 4. level
INSERT INTO user_achievements (user_id, achievement_id)
SELECT x.user_id, a.id
FROM user_xp x
JOIN achievements a ON a.condition_type = 'level' AND x.current_level >= a.condition_value
ON CONFLICT DO NOTHING;

-- 5. xp_total
INSERT INTO user_achievements (user_id, achievement_id)
SELECT x.user_id, a.id
FROM user_xp x
JOIN achievements a ON a.condition_type = 'xp_total' AND x.total_xp >= a.condition_value
ON CONFLICT DO NOTHING;

-- 6. streak_days (vocal)
INSERT INTO user_achievements (user_id, achievement_id)
SELECT s.user_id, a.id
FROM user_streaks s
JOIN achievements a ON a.condition_type = 'streak_days'
WHERE GREATEST(s.current_streak, s.max_streak) >= a.condition_value
ON CONFLICT DO NOTHING;

-- 7. message_streak_days
INSERT INTO user_achievements (user_id, achievement_id)
SELECT ms.user_id, a.id
FROM user_message_streaks ms
JOIN achievements a ON a.condition_type = 'message_streak_days'
WHERE GREATEST(ms.current_streak, ms.max_streak) >= a.condition_value
ON CONFLICT DO NOTHING;

-- 8. quests_completed
INSERT INTO user_achievements (user_id, achievement_id)
SELECT sub.user_id, a.id
FROM (SELECT user_id, COUNT(*) AS cnt FROM user_quest_progress WHERE xp_claimed=TRUE GROUP BY user_id) sub
JOIN achievements a ON a.condition_type = 'quests_completed' AND sub.cnt >= a.condition_value
ON CONFLICT DO NOTHING;

-- 9. unique_voice_channels
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'unique_voice_channels'
WHERE COALESCE(u.unique_voice_channels_count, 0) >= a.condition_value
ON CONFLICT DO NOTHING;

-- 10. voice_night_minutes
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'voice_night_minutes'
WHERE COALESCE(u.voice_night_minutes, 0) >= a.condition_value
ON CONFLICT DO NOTHING;

-- 11. voice_morning_minutes
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'voice_morning_minutes'
WHERE COALESCE(u.voice_morning_minutes, 0) >= a.condition_value
ON CONFLICT DO NOTHING;

-- 12. longest_session_minutes
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'longest_session_minutes'
WHERE COALESCE(u.longest_session_minutes, 0) >= a.condition_value
ON CONFLICT DO NOTHING;

-- 13. consecutive_voice_days
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'consecutive_voice_days'
WHERE COALESCE(u.consecutive_voice_days, 0) >= a.condition_value
ON CONFLICT DO NOTHING;

-- 14. articles_published / articles_written
INSERT INTO user_achievements (user_id, achievement_id)
SELECT sub.author_id, a.id
FROM (SELECT author_id, COUNT(*) AS cnt FROM articles WHERE published=TRUE GROUP BY author_id) sub
JOIN achievements a ON a.condition_type IN ('articles_published','articles_written') AND sub.cnt >= a.condition_value
ON CONFLICT DO NOTHING;

-- 15. comments_posted
INSERT INTO user_achievements (user_id, achievement_id)
SELECT sub.user_id, a.id
FROM (SELECT user_id, COUNT(*) AS cnt FROM article_comments GROUP BY user_id) sub
JOIN achievements a ON a.condition_type = 'comments_posted' AND sub.cnt >= a.condition_value
ON CONFLICT DO NOTHING;

-- 16. votes_cast
INSERT INTO user_achievements (user_id, achievement_id)
SELECT sub.user_id, a.id
FROM (SELECT user_id, COUNT(*) AS cnt FROM article_votes GROUP BY user_id) sub
JOIN achievements a ON a.condition_type = 'votes_cast' AND sub.cnt >= a.condition_value
ON CONFLICT DO NOTHING;

-- 17. commands_used
INSERT INTO user_achievements (user_id, achievement_id)
SELECT sub.user_id, a.id
FROM (SELECT user_id, COALESCE(SUM(usage_count),0) AS cnt FROM user_command_stats GROUP BY user_id) sub
JOIN achievements a ON a.condition_type = 'commands_used' AND sub.cnt >= a.condition_value
ON CONFLICT DO NOTHING;

-- 18. blague_count
INSERT INTO user_achievements (user_id, achievement_id)
SELECT cs.user_id, a.id
FROM user_command_stats cs
JOIN achievements a ON a.condition_type = 'blague_count' AND cs.usage_count >= a.condition_value
WHERE cs.command_name = 'blague'
ON CONFLICT DO NOTHING;

-- 19. confess_count
INSERT INTO user_achievements (user_id, achievement_id)
SELECT cs.user_id, a.id
FROM user_command_stats cs
JOIN achievements a ON a.condition_type = 'confess_count' AND cs.usage_count >= a.condition_value
WHERE cs.command_name = 'confess'
ON CONFLICT DO NOTHING;

-- 20. bumps
INSERT INTO user_achievements (user_id, achievement_id)
SELECT b.user_id, a.id
FROM user_bump_stats b
JOIN achievements a ON a.condition_type = 'bumps' AND b.bump_count >= a.condition_value
ON CONFLICT DO NOTHING;

-- 21. invites
INSERT INTO user_achievements (user_id, achievement_id)
SELECT i.user_id, a.id
FROM user_invite_stats i
JOIN achievements a ON a.condition_type = 'invites' AND i.invite_count >= a.condition_value
ON CONFLICT DO NOTHING;

-- 22. messages_multi_channel
INSERT INTO user_achievements (user_id, achievement_id)
SELECT sub.user_id, a.id
FROM (SELECT user_id, COUNT(DISTINCT channel_id) AS cnt FROM user_message_stats GROUP BY user_id) sub
JOIN achievements a ON a.condition_type = 'messages_multi_channel' AND sub.cnt >= a.condition_value
ON CONFLICT DO NOTHING;

-- 23. days_on_server
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'days_on_server'
WHERE EXTRACT(DAY FROM NOW() - u.created_at)::int >= a.condition_value
ON CONFLICT DO NOTHING;

-- 24. warn_free_days
INSERT INTO user_achievements (user_id, achievement_id)
SELECT u.user_id, a.id
FROM user_voice_data u
JOIN achievements a ON a.condition_type = 'warn_free_days'
WHERE EXTRACT(DAY FROM NOW() - COALESCE(
    (SELECT TO_TIMESTAMP(MAX(create_time)) FROM warn w WHERE w.user_id = u.user_id),
    u.created_at
))::int >= a.condition_value
ON CONFLICT DO NOTHING;

-- 25. endorsements_received
INSERT INTO user_achievements (user_id, achievement_id)
SELECT r.user_id, a.id
FROM user_reputation r
JOIN achievements a ON a.condition_type = 'endorsements_received' AND r.total_count >= a.condition_value
ON CONFLICT DO NOTHING;

COMMIT;

SELECT
  (SELECT COUNT(*) FROM user_achievements) AS total_unlocked,
  (SELECT COUNT(DISTINCT user_id) FROM user_achievements) AS users_with_achievements,
  (SELECT COUNT(*) FROM user_achievements WHERE unlocked_at >= NOW() - INTERVAL '1 minute') AS just_unlocked;
