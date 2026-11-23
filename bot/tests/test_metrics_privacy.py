"""Métriques Prometheus : aucune donnée de modération nominative ni code d'invitation (constat I2)."""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

prometheus_client = pytest.importorskip("prometheus_client")
generate_latest = prometheus_client.generate_latest

import metrics  # noqa: E402
from utils import database  # noqa: E402

WARNED_NAME = "MembreAverti"
INVITE_CODE = "AbCdEf12"


def _run_refresh(monkeypatch):
    async def fetch(sql, *args):
        if "FROM warn" in sql and "GROUP BY user_id" in sql:
            return [{"warns": "1", "members": 3}, {"warns": "5+", "members": 1}]
        return []

    async def fetchval(sql, *args):
        return 0

    async def invite_stats():
        return {"total_codes": 2, "total_uses": 5, "uses_7d": 1}

    async def top_inviters(limit=15):
        return []

    async def active_invites():
        return [
            {"code": INVITE_CODE, "inviter_id": 9, "uses": 4, "max_uses": 0,
             "expires_at": None, "username": WARNED_NAME},
            {"code": "Zz99", "inviter_id": 9, "uses": 1, "max_uses": 0,
             "expires_at": datetime(2027, 1, 1, tzinfo=timezone.utc), "username": WARNED_NAME},
        ]

    monkeypatch.setattr(database.db_manager, "fetch", fetch)
    monkeypatch.setattr(database.db_manager, "fetchval", fetchval)
    monkeypatch.setattr(database.invite_manager, "get_invite_stats", invite_stats)
    monkeypatch.setattr(database.invite_manager, "get_top_inviters", top_inviters)
    monkeypatch.setattr(database.invite_manager, "get_active_invites", active_invites)
    asyncio.run(metrics.refresh())
    return generate_latest().decode()


def test_no_per_member_warn_count_nor_invite_codes(monkeypatch):
    out = _run_refresh(monkeypatch)
    assert "hermes_user_warn_count" not in out
    assert "hermes_invite_codes{" not in out
    assert INVITE_CODE not in out
    assert WARNED_NAME not in out


def test_warns_are_aggregated_by_bucket(monkeypatch):
    out = _run_refresh(monkeypatch)
    assert 'hermes_warned_members{warns="1"} 3.0' in out
    assert 'hermes_warned_members{warns="2"} 0.0' in out
    assert 'hermes_warned_members{warns="5+"} 1.0' in out
    assert "hermes_invites_permanent 1.0" in out
