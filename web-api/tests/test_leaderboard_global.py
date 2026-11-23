"""Classement global : score combiné, rang, recherche."""

ROW = {"user_id": 7, "username": "Kefir", "discord_avatar": None, "voice_minutes": 125,
       "total_messages": 40, "achievement_count": 2, "global_score": 565, "global_rank": 3}


def test_global_returns_rank_and_score(client, fake_db):
    fake_db.on("COUNT(*) FROM user_voice_data", 12)
    fake_db.on("RANK() OVER (ORDER BY global_score DESC)", [ROW])
    body = client.get("/leaderboard/global?page=2&limit=5").json()
    assert body["total"] == 12 and body["page"] == 2
    assert body["leaderboard"] == [{
        "user_id": "7", "username": "Kefir", "discord_avatar": None, "voice_formatted": "2h 5m",
        "total_messages": 40, "achievement_count": 2, "global_score": 565, "global_rank": 3,
    }]
    _, sql, args = [c for c in fake_db.calls if c[0] == "fetch"][0]
    assert "ILIKE" not in sql and args == (5, 5)


def test_global_search_keeps_global_rank(client, fake_db):
    fake_db.on("RANK() OVER (ORDER BY global_score DESC)", [ROW])
    client.get("/leaderboard/global?search=kef")
    _, sql, args = [c for c in fake_db.calls if c[0] == "fetch"][0]
    # Le rang est calculé sur tout le monde, puis filtré : la recherche ne renumérote pas.
    assert sql.index("RANK()") < sql.index("ILIKE")
    assert args == ("%kef%", 10, 0)
