"""get_role n'écrit l'avertissement « rôle disparu » qu'une fois par valeur."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import settings  # noqa: E402


class FakeGuild:
    roles: list = []

    def get_role(self, _id):
        return None


def test_missing_role_warns_once_per_value(caplog, monkeypatch):
    monkeypatch.setattr(settings, "_warned", set())
    monkeypatch.setitem(settings._cache, "admin_role", "123")
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            assert settings.get_role(FakeGuild(), "admin_role") is None
    assert len([r for r in caplog.records if "n'existe plus" in r.getMessage()]) == 1

    # Nouvelle valeur réglée, toujours introuvable : nouvel avertissement.
    monkeypatch.setitem(settings._cache, "admin_role", "456")
    with caplog.at_level(logging.WARNING):
        settings.get_role(FakeGuild(), "admin_role")
    assert len([r for r in caplog.records if "n'existe plus" in r.getMessage()]) == 2
