"""Récompense des défis versée automatiquement, une seule fois, sans /quest-claim."""
import asyncio
import types

from cogs.gamification import weekly_quests as wq


class FakeXP:
    def __init__(self):
        self.awarded = []

    async def award_xp(self, user_id, amount, source=""):
        self.awarded.append((user_id, amount, source))


class FakeBot:
    def __init__(self, xp):
        self.cogs = {"XPCog": xp}

    def get_cog(self, name):
        return self.cogs.get(name)


def make_cog(monkeypatch, claimed_ids=None, pending=None):
    """claimed_ids : défis dont la récompense est déjà versée (claim_xp renvoie None)."""
    claimed = set(claimed_ids or [])
    notifications = []

    async def claim_xp(user_id, quest_id):
        if (user_id, quest_id) in claimed:
            return None
        claimed.add((user_id, quest_id))
        return 150

    async def unclaimed_completed():
        return pending or []

    async def create(user_id, type_, title, description=None, related_id=None):
        notifications.append((user_id, type_, title, description))

    monkeypatch.setattr(wq, "quest_manager", types.SimpleNamespace(
        claim_xp=claim_xp, unclaimed_completed=unclaimed_completed))
    monkeypatch.setattr(wq, "notification_manager", types.SimpleNamespace(create=create))
    xp = FakeXP()
    cog = wq.WeeklyQuestsCog.__new__(wq.WeeklyQuestsCog)  # sans démarrer la tâche planifiée
    cog.bot = FakeBot(xp)
    return cog, xp, notifications


QUEST = {"id": 9, "title": "Bavard", "icon": "💬", "xp_reward": 150, "target_value": 50}


def test_completed_quest_is_rewarded_automatically(monkeypatch):
    cog, xp, notes = make_cog(monkeypatch)
    asyncio.run(cog.notify(7, QUEST))
    assert xp.awarded == [(7, 150, "quest")]
    assert notes == [(7, "quest_complete", "Défi complété : Bavard", "+150 XP ajoutés automatiquement")]
    assert "/quest-claim" not in notes[0][3]


def test_reward_is_paid_only_once(monkeypatch):
    cog, xp, notes = make_cog(monkeypatch)
    asyncio.run(cog.notify(7, QUEST))
    asyncio.run(cog.notify(7, QUEST))
    assert xp.awarded == [(7, 150, "quest")]
    assert len(notes) == 1


def test_pending_rewards_are_caught_up(monkeypatch):
    pending = [dict(QUEST, user_id=7), dict(QUEST, user_id=8), dict(QUEST, id=10, user_id=8)]
    cog, xp, _ = make_cog(monkeypatch, claimed_ids={(8, 10)}, pending=pending)
    assert asyncio.run(cog.grant_pending()) == 2
    assert sorted(u for u, _, _ in xp.awarded) == [7, 8]


def test_quest_claim_command_removed():
    names = {c.name for c in wq.WeeklyQuestsCog.__cog_app_commands__}
    assert "quest-claim" not in names
    assert "quests" in names
