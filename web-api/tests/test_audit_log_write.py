import asyncio


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
