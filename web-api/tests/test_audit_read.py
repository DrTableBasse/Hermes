"""Lecture du journal : filtres, pagination, facettes et export CSV."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def _row(id_=1, **over):
    row = {
        "id": id_, "occurred_at": datetime(2026, 11, 23, 10, 0, tzinfo=PARIS),
        "kind": "sanction", "action": "ban", "source": "site",
        "actor_id": 279205522970902528, "actor_name": "Kéfir",
        "target_id": 42, "target_name": "Troll", "channel_id": None,
        "channel_name": None, "success": True, "details": {"reason": "spam"},
    }
    row.update(over)
    return row


def test_filters_combine_and_parametrize():
    from routes.audit import build_audit_filters
    where, args = build_audit_filters({"kind": "command,sanction", "actor": "Kéfir", "success": "false"})
    assert "kind = ANY(" in where and "actor_name ILIKE" in where and "success =" in where
    assert ["command", "sanction"] in args and "%Kéfir%" in args and False in args
    assert "Kéfir" not in where and "sanction" not in where  # valeurs jamais dans le SQL


def test_numeric_actor_is_exact_id():
    from routes.audit import build_audit_filters
    where, args = build_audit_filters({"actor": "279205522970902528"})
    assert "actor_id =" in where and 279205522970902528 in args
    assert "ILIKE" not in where


def test_numeric_target_and_channel():
    from routes.audit import build_audit_filters
    where, args = build_audit_filters({"target": "42", "channel_id": "99"})
    assert "target_id =" in where and "channel_id =" in where
    assert 42 in args and 99 in args


def test_no_filters_means_no_where():
    from routes.audit import build_audit_filters
    assert build_audit_filters({}) == ("", [])


def test_date_range_paris_inclusive():
    from routes.audit import build_audit_filters
    where, args = build_audit_filters({"from": "2026-11-01", "to": "2026-11-23"})
    assert "occurred_at >=" in where and "occurred_at <" in where
    start = datetime(2026, 11, 1, tzinfo=PARIS)
    end = datetime(2026, 11, 24, tzinfo=PARIS)
    assert start in args and end in args
    assert args.index(start) < args.index(end)
    # le 23 à 23:59:59 Paris reste dans la borne exclusive du 24 à 00:00
    assert datetime(2026, 11, 23, 23, 59, 59, tzinfo=PARIS) < end


def test_date_range_paris_handles_dst_change():
    from routes.audit import build_audit_filters
    _, args = build_audit_filters({"to": "2026-03-28"})  # le lendemain passe à l'heure d'été
    end = [a for a in args if isinstance(a, datetime)][0]
    assert end.utcoffset() == timedelta(hours=1)
    assert end == datetime(2026, 3, 29, 0, 0, tzinfo=PARIS)


def test_search_q_covers_action_names_and_details():
    from routes.audit import build_audit_filters
    where, args = build_audit_filters({"q": "spam"})
    for col in ("action ILIKE", "actor_name ILIKE", "target_name ILIKE", "details::text ILIKE"):
        assert col in where
    assert "%spam%" in args and "spam" not in where


def test_like_wildcards_are_escaped():
    from routes.audit import build_audit_filters
    _, args = build_audit_filters({"q": "100%_x"})
    assert "%100\\%\\_x%" in args


def test_unknown_kind_or_source_is_422(client, admin_session):
    assert client.get("/admin/audit?kind=pirate").status_code == 422
    assert client.get("/admin/audit?source=ailleurs").status_code == 422
    assert client.get("/admin/audit?kind=sanction,pirate").status_code == 422


def test_invalid_date_is_422(client, admin_session):
    assert client.get("/admin/audit?from=2026-13-40").status_code == 422
    assert client.get("/admin/audit?to=hier").status_code == 422
    assert client.get("/admin/audit.csv?from=2026-13-40").status_code == 422
    # Hors bornes (2000-2100) : 422, jamais 500 (dépassement de date).
    assert client.get("/admin/audit?to=9999-12-31").status_code == 422
    assert client.get("/admin/audit?from=0001-01-01").status_code == 422
    assert client.get("/admin/audit.csv?to=9999-12-31").status_code == 422


def test_invalid_success_is_422(client, admin_session):
    assert client.get("/admin/audit?success=peutetre").status_code == 422


def test_audit_requires_admin(client, member_session):
    assert client.get("/admin/audit").status_code == 403
    assert client.get("/admin/audit.csv").status_code == 403
    assert client.get("/admin/audit/facets").status_code == 403


def test_audit_requires_login(client):
    assert client.get("/admin/audit").status_code == 401


def test_audit_returns_page_shape(client, admin_session, fake_db):
    fake_db.on("count(*)", 120)
    fake_db.on("from audit_events", [_row(), _row(2, kind="voice", action="self_mute",
                                                    actor_id=None, details={"active": False})])
    r = client.get("/admin/audit?page=2")
    assert r.status_code == 200
    body = r.json()
    assert (body["total"], body["page"], body["pages"]) == (120, 2, 3)
    first, second = body["events"]
    assert set(first) == {"id", "occurred_at", "kind", "action", "source", "actor_id", "actor_name",
                          "target_id", "target_name", "channel_id", "channel_name", "success", "details"}
    assert first["actor_id"] == "279205522970902528" and first["target_id"] == "42"
    assert first["channel_id"] is None and second["actor_id"] is None
    assert first["occurred_at"].startswith("2026-11-23T10:00:00")
    assert second["details"] == {"active": False}
    select = [c for c in fake_db.calls if c[0] == "fetch"][0]
    assert "ORDER BY occurred_at DESC, id DESC" in select[1]
    assert select[2][-2:] == (50, 50)  # LIMIT 50 OFFSET 50 (page 2)


def test_audit_applies_filters_as_parameters(client, admin_session, fake_db):
    fake_db.on("count(*)", 0)
    r = client.get("/admin/audit?kind=voice&action=join,leave&source=discord&q=x'--")
    assert r.status_code == 200
    assert r.json() == {"events": [], "total": 0, "page": 1, "pages": 1}
    _, sql, args = [c for c in fake_db.calls if c[0] == "fetch"][0]
    assert "x'--" not in sql and ["voice"] in args and ["join", "leave"] in args


def test_csv_neutralises_formulas():
    from routes.audit import csv_cell
    assert csv_cell("=HYPERLINK(\"x\")").startswith("'")
    for bad in ("+1", "-1", "@SUM", "\tx", "\rx"):
        assert csv_cell(bad) == "'" + bad
    assert csv_cell("Kéfir") == "Kéfir"
    assert csv_cell("") == ""


def test_csv_headers_and_disposition(client, admin_session, fake_db):
    r = client.get("/admin/audit.csv")
    assert r.headers["content-type"].startswith("text/csv")
    assert "utf-8" in r.headers["content-type"].lower()
    assert "attachment" in r.headers["content-disposition"]
    assert 'filename="journal-hermes-' in r.headers["content-disposition"]
    assert r.headers["content-disposition"].endswith('.csv"')
    assert r.content.startswith("﻿Date;Type;Action;Source;Auteur;Cible;Salon;Succès;Détails".encode("utf-8"))


def test_csv_rows_are_escaped_and_capped(client, admin_session, fake_db):
    fake_db.on("from audit_events", [_row(actor_name="=cmd|' /C calc'!A0", target_name='a;b"c',
                                          success=False)])
    r = client.get("/admin/audit.csv?kind=sanction")
    lines = r.content.decode("utf-8-sig").splitlines()
    assert len(lines) == 2
    assert "'=cmd" in lines[1] and '"a;b""c"' in lines[1]
    assert lines[1].split(";")[0].startswith("2026-11-23")
    _, sql, args = [c for c in fake_db.calls if c[0] == "fetch"][0]
    assert "LIMIT" in sql and 10000 in args


def test_facets_shape_and_cache(client, admin_session, fake_db):
    import routes.audit as audit
    audit._facets_cache.update(at=0.0, value=None)
    fake_db.on("select distinct kind, action", [
        {"kind": "voice", "action": "leave"}, {"kind": "voice", "action": "join"},
        {"kind": "sanction", "action": "ban"}])
    fake_db.on("channel_name is not null", [{"id": 5, "name": "général"}])
    body = client.get("/admin/audit/facets").json()
    assert body == {"kinds": {"sanction": ["ban"], "voice": ["join", "leave"]},
                    "channels": [{"id": "5", "name": "général"}]}
    n = len(fake_db.calls)
    assert client.get("/admin/audit/facets").json() == body
    assert len(fake_db.calls) == n  # servi par le cache de 60 s


def test_analytics_reads_audit_events(client, admin_session, fake_db):
    fake_db.on("from audit_events", [])
    client.get("/admin/analytics")
    sqls = [c[1] for c in fake_db.calls if "audit_events" in c[1]]
    assert sqls and "admin_logs" not in sqls[0]
    assert "kind = 'sanction'" in sqls[0] and "occurred_at" in sqls[0]


def test_old_admin_logs_route_is_gone(client, admin_session):
    assert client.get("/admin/logs").status_code == 404
