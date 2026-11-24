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

    pending_rows = list(pending or [])  # (user_id, quest_id, xp)

    async def pending_users():
        return sorted({u for u, q, _ in pending_rows if (u, q) not in claimed})

    async def claim_all_for(user_id):
        rows = [(q, x) for u, q, x in pending_rows if u == user_id and (u, q) not in claimed]
        for q, _ in rows:
            claimed.add((user_id, q))
        return sum(x for _, x in rows), len(rows)

    async def create(user_id, type_, title, description=None, related_id=None):
        notifications.append((user_id, type_, title, description))

    monkeypatch.setattr(wq, "quest_manager", types.SimpleNamespace(
        claim_xp=claim_xp, pending_users=pending_users, claim_all_for=claim_all_for))
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


def test_pending_rewards_of_all_weeks_are_caught_up_with_one_notice_per_member(monkeypatch):
    # Membre 7 : deux défis (dont une ancienne semaine) ; membre 8 : un défi déjà versé + un en attente.
    pending = [(7, 1, 100), (7, 2, 50), (8, 10, 80), (8, 11, 30)]
    cog, xp, notes = make_cog(monkeypatch, claimed_ids={(8, 10)}, pending=pending)
    assert asyncio.run(cog.grant_pending()) == 2
    assert sorted(xp.awarded) == [(7, 150, "quest"), (8, 30, "quest")]
    assert sorted(n[3] for n in notes) == ["+150 XP pour 2 défis terminés", "+30 XP pour 1 défi terminé"]
    # Relancé : plus rien à verser.
    assert asyncio.run(cog.grant_pending()) == 0
    assert len(xp.awarded) == 2


def test_quest_claim_command_removed():
    names = {c.name for c in wq.WeeklyQuestsCog.__cog_app_commands__}
    assert "quest-claim" not in names
    assert "quests" in names
