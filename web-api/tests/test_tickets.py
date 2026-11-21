"""Tickets : GET /tickets (admin), GET /tickets/mine (membre), transcription (propriétaire ou admin)."""
from datetime import datetime, timezone

import pytest

from middleware import auth_middleware

NOW = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)


def _row(id_, user_id, transcript=True):
    return {
        "id": id_, "ticket_number": id_, "user_id": user_id, "username": "Camille",
        "subject": "Rôle", "status": "closed", "created_at": NOW, "closed_at": NOW,
        "has_transcript": transcript,
    }


@pytest.fixture
def as_user(client, monkeypatch):
    def _as(discord_id, is_admin=False):
        async def fake_session(token):
            return {"sub": discord_id, "is_admin": is_admin, "is_redacteur": False}

        monkeypatch.setattr(auth_middleware, "_fetch_session", fake_session)
        client.cookies.set("better-auth.session_token", "tok")

    return _as


def test_mine_requires_session(client, fake_db):
    assert client.get("/tickets/mine").status_code == 401


def test_mine_filters_on_connected_member_with_bound_parameters(client, fake_db, as_user):
    as_user("100")
    fake_db.on("count(*)", 1)  # avant la règle suivante, qui capterait aussi le COUNT
    fake_db.on("from tickets t", [_row(7, 100)])
    r = client.get("/tickets/mine?status=open&page=2&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["tickets"][0]["id"] == 7 and body["tickets"][0]["user_id"] == "100"
    assert (body["total"], body["page"], body["limit"]) == (1, 2, 5)
    method, sql, args = fake_db.calls[0]
    assert "t.user_id = $2" in sql and "t.status = $1" in sql
    assert args == ("open", 100, 5, 5)  # statut, membre, limite, décalage (page 2 × 5)
    assert "100" not in sql and "open" not in sql


def test_mine_is_available_to_admin_for_their_own_tickets_only(client, fake_db, as_user):
    as_user("1", is_admin=True)
    fake_db.on("count(*)", 0)
    fake_db.on("from tickets t", [])
    assert client.get("/tickets/mine").status_code == 200
    assert fake_db.calls[0][2][0] == 1


def test_mine_rejects_invalid_status(client, fake_db, as_user):
    as_user("100")
    assert client.get("/tickets/mine?status=x';--").status_code == 422


def test_global_list_is_admin_only(client, fake_db, as_user):
    assert client.get("/tickets").status_code == 401
    as_user("100")
    assert client.get("/tickets").status_code == 403
    as_user("1", is_admin=True)
    fake_db.on("count(*)", 1)
    fake_db.on("from tickets t", [_row(7, 100)])
    r = client.get("/tickets?status=closed")
    assert r.status_code == 200 and r.json()["tickets"][0]["id"] == 7
    assert fake_db.calls[0][2] == ("closed", 20, 0)  # pas de filtre de membre


def test_transcript_without_session_is_401(client, fake_db):
    assert client.get("/tickets/7/transcript").status_code == 401


def test_transcript_owner_ok(client, fake_db, as_user):
    as_user("100")
    fake_db.on("from tickets where id", {"user_id": 100, "transcript_html": "<p>salut</p>"})
    r = client.get("/tickets/7/transcript")
    assert r.status_code == 200 and r.text == "<p>salut</p>"


def test_transcript_of_another_member_is_403(client, fake_db, as_user):
    as_user("999")
    fake_db.on("from tickets where id", {"user_id": 100, "transcript_html": "<p>secret</p>"})
    r = client.get("/tickets/7/transcript")
    assert r.status_code == 403 and "secret" not in r.text


def test_transcript_unknown_ticket_is_403_for_member_404_for_admin(client, fake_db, as_user):
    as_user("999")
    assert client.get("/tickets/404/transcript").status_code == 403
    as_user("1", is_admin=True)
    assert client.get("/tickets/404/transcript").status_code == 404


def test_transcript_admin_ok_and_missing_transcript_404(client, fake_db, as_user):
    as_user("1", is_admin=True)
    fake_db.on("from tickets where id", {"user_id": 100, "transcript_html": "<p>x</p>"})
    assert client.get("/tickets/7/transcript").status_code == 200
    fake_db.rules.clear()
    fake_db.on("from tickets where id", {"user_id": 100, "transcript_html": None})
    assert client.get("/tickets/7/transcript").status_code == 404
