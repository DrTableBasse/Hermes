"""Rôles admin/rédacteur : lus dans bot_settings, repli sur l'environnement."""
import auth


async def test_roles_from_bot_settings(fake_db):
    fake_db.on("from bot_settings", [
        {"key": "admin_role", "value": "111"},
        {"key": "redacteur_role", "value": "222"},
    ])
    refs = await auth.staff_role_refs()
    assert refs == {"admin": {"id": "111"}, "redacteur": {"id": "222"}}


async def test_roles_fallback_on_env(fake_db, monkeypatch):
    monkeypatch.setenv("ADMIN_ROLE_NAME", "Chefs")
    monkeypatch.delenv("REDACTEUR_ROLE_NAME", raising=False)
    fake_db.on("from bot_settings", [{"key": "admin_role", "value": ""}])
    refs = await auth.staff_role_refs()
    assert refs == {"admin": {"name": "Chefs"}, "redacteur": {"name": "rédacteur"}}


def test_member_has_role_by_id_or_name():
    guild_roles = {"111": "Administration", "333": "rédacteur"}
    assert auth.member_has_role({"id": "111"}, ["111"], guild_roles)
    assert not auth.member_has_role({"id": "111"}, ["333"], guild_roles)
    assert auth.member_has_role({"name": "rédacteur"}, ["333"], guild_roles)
    assert not auth.member_has_role({"name": "Chefs"}, ["111", "333"], guild_roles)
