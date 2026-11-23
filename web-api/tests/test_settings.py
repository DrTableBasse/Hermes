import bot_client

ADMIN = {"discordId": "42", "isAdmin": True, "isRedacteur": False, "sitePermissions": []}
USER = {"discordId": "43", "isAdmin": False, "isRedacteur": False, "sitePermissions": []}


def _login(client, fake_db, row):
    fake_db.on("from session", row)
    client.cookies.set("better-auth.session_token", "tok")


def test_settings_requires_admin(client, fake_db):
    _login(client, fake_db, USER)
    assert client.get("/admin/settings").status_code == 403
    assert client.put("/admin/settings/bump_role_threshold", json={"value": "5"}).status_code == 403


def test_put_setting_validates(client, fake_db):
    _login(client, fake_db, ADMIN)
    r = client.put("/admin/settings/bump_role_threshold", json={"value": "abc"})
    assert r.status_code == 422
    assert not [c for c in fake_db.calls if "insert into bot_settings" in c[1].lower()]


def test_put_setting_reloads_bot(client, fake_db, monkeypatch):
    _login(client, fake_db, ADMIN)
    posted = []

    async def fake_post(path, json=None, timeout=1.5):
        posted.append(path)
        return {"ok": True}

    monkeypatch.setattr(bot_client, "bot_post", fake_post)
    r = client.put("/admin/settings/bump_role_threshold", json={"value": "30"})
    assert r.status_code == 200
    assert r.json()["value"] == "30"
    assert posted == ["/settings/reload"]
    writes = [c for c in fake_db.calls if "insert into bot_settings" in c[1].lower()]
    assert writes and writes[0][2][:2] == ("bump_role_threshold", "30")


def test_get_settings_groups(client, fake_db, monkeypatch):
    _login(client, fake_db, ADMIN)
    fake_db.on("from bot_settings", [{"key": "welcome_channel", "value": "10"}])

    async def fake_get(path, timeout=1.5):
        if path == "/discord/channels":
            return {"channels": [{"id": "10", "name": "accueil", "type": "text", "category": None}]}
        return {"roles": []}

    monkeypatch.setattr(bot_client, "bot_get", fake_get)
    data = client.get("/admin/settings").json()
    items = {i["key"]: i for g in data["groups"] for i in g["items"]}
    assert items["welcome_channel"]["resolved"] == {"id": "10", "name": "accueil", "exists": True}
    assert items["bump_role_threshold"]["resolved"] is None


def test_public_settings_only_public(client, fake_db, monkeypatch):
    monkeypatch.setenv("GUILD_ID", "999")
    fake_db.on("from bot_settings", [
        {"key": "invite_url", "value": "https://discord.gg/abc"},
        {"key": "ticket_panel_channel", "value": "77"},
        {"key": "admin_log_channel", "value": "5"},
    ])
    r = client.get("/settings/public")
    assert r.status_code == 200
    assert r.json() == {
        "invite_url": "https://discord.gg/abc",
        "ticket_panel_url": "https://discord.com/channels/999/77",
    }


def test_put_empty_value_deletes_row(client, fake_db, monkeypatch):
    _login(client, fake_db, ADMIN)

    async def fake_post(path, json=None, timeout=1.5):
        return {"ok": True}

    monkeypatch.setattr(bot_client, "bot_post", fake_post)
    r = client.put("/admin/settings/welcome_channel", json={"value": "  "})
    assert r.status_code == 200
    assert r.json()["value"] == ""
    deletes = [c for c in fake_db.calls if c[1].lower().startswith("delete from bot_settings")]
    assert deletes and deletes[0][2] == ("welcome_channel",)
    assert not [c for c in fake_db.calls if "insert into bot_settings" in c[1].lower()]
