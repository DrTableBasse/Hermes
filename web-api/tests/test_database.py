"""Budget de temps du pool PostgreSQL (constat I4 frontend : échec rapide si la base bloque)."""
import asyncio

import database


def test_pool_has_connect_and_command_timeouts(monkeypatch):
    seen = {}

    async def fake_create_pool(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(database.asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(database, "_pool", None)
    asyncio.run(database.init_pool())
    assert seen["timeout"] == database.POOL_TIMEOUT_S <= 5
    assert seen["command_timeout"] == database.COMMAND_TIMEOUT_S <= 10


def test_acquire_waits_at_most_the_pool_timeout(monkeypatch):
    seen = {}

    class FakePool:
        async def acquire(self, timeout=None):
            seen["timeout"] = timeout
            return "conn"

        async def release(self, conn):
            seen["released"] = conn

    monkeypatch.setattr(database, "_pool", FakePool())

    async def run():
        async with database.get_conn() as conn:
            assert conn == "conn"

    asyncio.run(run())
    assert seen == {"timeout": database.POOL_TIMEOUT_S, "released": "conn"}
