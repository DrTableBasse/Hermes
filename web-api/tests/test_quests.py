"""GET /quests : colonnes réelles de user_quest_progress, statut dérivé, pas de route de réclamation."""
import asyncio
from datetime import date

from routes import quests


def test_list_quests_uses_real_columns_and_derives_status(monkeypatch):
    calls = []

    async def fake_fetch(sql, *args):
        calls.append((sql, args))
        return [{"id": 1, "status": "claimed", "current_progress": 3}]

    monkeypatch.setattr(quests.db, "fetch", fake_fetch)
    result = asyncio.run(quests.list_quests(user={"sub": "42"}))

    assert result == {"quests": [{"id": 1, "status": "claimed", "current_progress": 3}]}
    sql, args = calls[0]
    assert args == (42, date.today())
    # Les colonnes inexistantes qui provoquaient une erreur 500 ne sont plus lues.
    assert "up.current_progress" not in sql and "up.status" not in sql
    assert "up.progress_value" in sql and "up.xp_claimed" in sql and "up.completed" in sql
    assert "LEAST(COALESCE(up.progress_value, 0), q.target_value)" in sql  # pas de « 5 sur 3 »
    assert "'claimed'" in sql and "'completed'" in sql and "'active'" in sql


def test_no_claim_route():
    paths = {getattr(r, "path", "") for r in quests.router.routes}
    assert not any(p.endswith("/claim") for p in paths)
