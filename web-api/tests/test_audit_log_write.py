import asyncio
import json


def test_log_writes_audit_event_with_kind_and_source(fake_db):
    from routes.admin import _log
    fake_db.on("FROM user_voice_data", {"name": "Kéfir"})
    asyncio.run(_log("kick", 1, 2, {"reason": "spam"}))
    method, sql, args = [c for c in fake_db.calls if c[0] == "execute"][0]
    assert "INSERT INTO audit_events" in sql
    assert args[:4] == ("sanction", "kick", "site", 1)
    assert "admin_logs" not in sql


def test_log_kinds_cover_existing_actions():
    from routes.admin import KIND_OF_ACTION
    assert KIND_OF_ACTION["command_toggle"] == "setting"
    assert {KIND_OF_ACTION[a] for a in ("kick", "ban", "timeout", "warn", "delete_warn")} == {"sanction"}
    assert KIND_OF_ACTION["quest_deploy"] == "content"


def test_log_never_raises(fake_db):
    from routes.admin import _log

    def boom(*a):
        raise RuntimeError("db down")

    fake_db.on("INSERT INTO audit_events", boom)
    asyncio.run(_log("ban", 1, 2))  # ne lève pas
    assert any("INSERT INTO audit_events" in c[1] for c in fake_db.calls)


def test_log_success_false_is_written(fake_db):
    from routes.admin import _log
    asyncio.run(_log("ban", 1, 2, {"error": "x"}, success=False))
    method, sql, args = [c for c in fake_db.calls if c[0] == "execute"][0]
    assert "success" in sql
    assert args[-1] is False


def _failing_bot(monkeypatch):
    from fastapi import HTTPException
    from routes import admin

    async def boom(*a, **kw):
        raise HTTPException(status_code=403, detail="Rôle trop haut")

    monkeypatch.setattr(admin, "_bot", boom)


def test_failed_site_sanction_is_logged_then_raised(fake_db, monkeypatch):
    import pytest
    from fastapi import HTTPException
    from routes import admin

    _failing_bot(monkeypatch)
    admin_user = {"sub": "1", "is_admin": True}
    calls = [
        lambda: admin.kick(admin.ModerationAction(user_id="2", reason="r"), admin_user),
        lambda: admin.ban(admin.ModerationAction(user_id="2", reason="r"), admin_user),
        lambda: admin.timeout(admin.ModerationAction(user_id="2", reason="r", duration=5), admin_user),
        lambda: admin.add_warn(admin.ModerationAction(user_id="2", reason="r"), admin_user),
    ]
    for call in calls:
        fake_db.calls.clear()
        with pytest.raises(HTTPException) as exc:
            asyncio.run(call())
        assert exc.value.status_code == 403
        inserts = [c for c in fake_db.calls if c[0] == "execute" and "INSERT INTO audit_events" in c[1]]
        assert len(inserts) == 1
        args = inserts[0][2]
        assert args[0] == "sanction" and args[-1] is False
        assert json.loads(args[7])["error"] == "Rôle trop haut"


def test_successful_site_sanction_logs_success_true(fake_db, monkeypatch):
    from routes import admin

    async def ok(*a, **kw):
        return {"ok": True}

    monkeypatch.setattr(admin, "_bot", ok)
    asyncio.run(admin.kick(admin.ModerationAction(user_id="2", reason="r"), {"sub": "1", "is_admin": True}))
    inserts = [c for c in fake_db.calls if c[0] == "execute" and "INSERT INTO audit_events" in c[1]]
    assert len(inserts) == 1 and inserts[0][2][-1] is True
