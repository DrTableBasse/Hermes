"""API interne : rang Discord d'un membre et rôles enrichis (étape 2, tâche 4)."""
import os
import sys
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord  # noqa: E402
import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

# prometheus_client n'est requis que pour /metrics ; absent du poste, un substitut sert
# le temps d'importer api.py, puis est retiré (les autres tests voient le vrai état).
try:
    import prometheus_client  # noqa: F401
    import api  # noqa: E402
except ImportError:
    _stub = types.ModuleType("prometheus_client")
    _stub.CONTENT_TYPE_LATEST = "text/plain"
    _stub.generate_latest = lambda *a, **k: b""
    sys.modules["prometheus_client"] = _stub
    try:
        import api  # noqa: E402
    finally:
        del sys.modules["prometheus_client"]

TOKEN = "jeton-de-test"


def _role(rid, name, position, *, managed=False, default=False, color=0):
    return SimpleNamespace(
        id=rid, name=name, position=position, managed=managed,
        color=SimpleNamespace(value=color), is_default=lambda: default,
    )


EVERYONE = _role(1, "@everyone", 0, default=True)
MEMBRE = _role(10, "Membre", 1)
MODO = _role(20, "Modo", 5, color=0x112233)
BOT_ROLE = _role(30, "Hermes", 8, managed=True)


class FakeGuild:
    owner_id = 999

    def __init__(self, members):
        self.roles = [EVERYONE, MODO, MEMBRE, BOT_ROLE]
        self._members = {m.id: m for m in members}

    def get_member(self, user_id):
        return self._members.get(user_id)

    async def fetch_member(self, user_id):
        raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Member")


def _member(mid, roles):
    roles = [EVERYONE, *roles]
    return SimpleNamespace(id=mid, roles=roles, top_role=max(roles, key=lambda r: r.position))


@pytest.fixture
def http(monkeypatch):
    guild = FakeGuild([
        _member(42, [MEMBRE, MODO]),
        _member(999, []),
        _member(7, []),
    ])
    monkeypatch.setattr(api, "BOT_API_TOKEN", TOKEN)
    monkeypatch.setattr(api, "_get_guild", lambda: guild)
    client = TestClient(api.app)
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    return client


def test_rank_returns_top_role_position_and_role_ids(http):
    r = http.get("/discord/members/42/rank")
    assert r.status_code == 200
    body = r.json()
    assert body["top_position"] == 5
    assert body["is_owner"] is False
    assert sorted(body["role_ids"]) == ["10", "20"]  # @everyone exclu


def test_rank_flags_owner(http):
    body = http.get("/discord/members/999/rank").json()
    assert body == {"top_position": 0, "is_owner": True, "role_ids": []}


def test_rank_member_without_roles_is_at_zero(http):
    assert http.get("/discord/members/7/rank").json()["top_position"] == 0


def test_rank_unknown_member_is_404(http):
    assert http.get("/discord/members/123/rank").status_code == 404


def test_rank_requires_token(http):
    r = http.get("/discord/members/42/rank", headers={"Authorization": "Bearer faux"})
    assert r.status_code == 401


def test_roles_expose_position_and_managed(http):
    roles = http.get("/discord/roles").json()["roles"]
    assert [r["id"] for r in roles] == ["30", "20", "10"]  # position décroissante, sans @everyone
    assert roles[0] == {"id": "30", "name": "Hermes", "color": 0, "position": 8, "managed": True}
    assert roles[1] == {"id": "20", "name": "Modo", "color": 0x112233, "position": 5, "managed": False}
