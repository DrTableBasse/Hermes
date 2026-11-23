"""Fixtures partagées des tests web-api.

- ``fake_db`` : remplace les accesseurs de ``database`` par des fonctions programmables.
- ``client`` : ``TestClient`` sur ``main.app``, sans pool PostgreSQL réel.
"""
import os
import sys

import pytest

# Rend les modules de web-api (main, database, ...) importables depuis tests/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402


class FakeDB:
    """Base factice : ``on(fragment, result)`` programme la réponse d'une requête.

    Une requête SQL reçoit le résultat de la première règle dont le fragment
    (insensible à la casse) est contenu dans le SQL ; sans règle : ``None`` pour
    ``fetchrow``/``fetchval``, ``[]`` pour ``fetch``, ``"OK"`` pour ``execute``.
    ``result`` peut être une valeur ou un callable ``(sql, *args) -> valeur``.
    Tous les appels sont enregistrés dans ``calls`` sous la forme ``(méthode, sql, args)``.
    """

    def __init__(self):
        self.rules = []
        self.calls = []

    def on(self, sql_fragment, result):
        self.rules.append((sql_fragment.lower(), result))

    def _answer(self, method, sql, args, default):
        self.calls.append((method, sql, args))
        for fragment, result in self.rules:
            if fragment in sql.lower():
                return result(sql, *args) if callable(result) else result
        return default

    async def fetch(self, sql, *args):
        return self._answer("fetch", sql, args, [])

    async def fetchrow(self, sql, *args):
        return self._answer("fetchrow", sql, args, None)

    async def fetchval(self, sql, *args):
        return self._answer("fetchval", sql, args, None)

    async def execute(self, sql, *args):
        return self._answer("execute", sql, args, "OK")


@pytest.fixture
def fake_db(monkeypatch):
    fake = FakeDB()
    for name in ("fetch", "fetchrow", "fetchval", "execute"):
        monkeypatch.setattr(database, name, getattr(fake, name))
    return fake


@pytest.fixture
def client(monkeypatch):
    async def _noop():
        return None

    monkeypatch.setattr(database, "init_pool", _noop)
    monkeypatch.setattr(database, "close_pool", _noop)
    # main monte /app/media au chargement ; ce dossier n'existe pas hors Docker.
    from starlette.staticfiles import StaticFiles

    original_init = StaticFiles.__init__
    monkeypatch.setattr(
        StaticFiles, "__init__",
        lambda self, *a, **kw: original_init(self, *a, **{**kw, "check_dir": False}),
    )
    import main  # import tardif, une fois le montage neutralisé
    from fastapi.testclient import TestClient

    with TestClient(main.app) as test_client:
        yield test_client


def _fake_session(monkeypatch, client, *, is_admin, permissions=()):
    import middleware.auth_middleware as auth_mw

    async def fake_fetch_session(token):
        return {
            "sub": "1", "is_admin": is_admin,
            "is_redacteur": "articles.write" in permissions,
            "permissions": frozenset(permissions),
        }

    monkeypatch.setattr(auth_mw, "_fetch_session", fake_fetch_session)
    client.cookies.set("better-auth.session_token", "tok")
    return client


@pytest.fixture
def admin_session(monkeypatch, client):
    """Session administrateur simulée (cookie + ``_fetch_session`` remplacé)."""
    return _fake_session(monkeypatch, client, is_admin=True)


@pytest.fixture
def member_session(monkeypatch, client):
    """Session membre simple (non admin) simulée."""
    return _fake_session(monkeypatch, client, is_admin=False)


@pytest.fixture
def session_with(monkeypatch, client):
    """Fabrique de session non admin munie d'un ensemble de droits : ``session_with({"admin.view"})``."""
    def _with(permissions=(), *, is_admin=False):
        return _fake_session(monkeypatch, client, is_admin=is_admin, permissions=tuple(permissions))
    return _with
