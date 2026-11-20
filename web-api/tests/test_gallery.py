"""Tests de la galerie : GET /gallery (public) et routes admin."""
from datetime import datetime, timezone

import pytest

import middleware.auth_middleware as auth_mw


def _row(id_=1, kind="image", file_name="a.png", clip_url=None, provider=None, hidden=False):
    return {"id": id_, "kind": kind, "file_name": file_name, "clip_url": clip_url,
            "clip_provider": provider, "caption": "légende", "hidden": hidden,
            "author_id": 42, "username": "Saucisse", "discord_avatar": "https://cdn/a.png",
            "created_at": datetime(2026, 11, 20, tzinfo=timezone.utc)}


def _session(monkeypatch, is_admin):
    async def fake_fetch_session(token):
        return {"sub": "1", "is_admin": is_admin, "is_redacteur": False}
    monkeypatch.setattr(auth_mw, "_fetch_session", fake_fetch_session)


def test_gallery_hides_hidden(client, fake_db):
    fake_db.on("from gallery_items", lambda sql, *a: [_row()])
    r = client.get("/gallery?limit=30")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["url"] == "/media/gallery/a.png"
    assert item["author"] == {"id": "42", "name": "Saucisse", "avatar": "https://cdn/a.png"}
    sql = next(s for m, s, a in fake_db.calls if "gallery_items" in s)
    assert "hidden = FALSE" in sql
    assert "ORDER BY created_at DESC" in sql


def test_gallery_clip_item(client, fake_db):
    fake_db.on("from gallery_items", [_row(kind="clip", file_name=None,
                                           clip_url="https://youtu.be/x", provider="youtube")])
    item = client.get("/gallery").json()["items"][0]
    assert item["url"] == "https://youtu.be/x" and item["provider"] == "youtube"


def test_gallery_limit_bounded(client, fake_db):
    assert client.get("/gallery?limit=999").status_code == 422


def test_highlights_fallback_to_recent(client, fake_db):
    # aucune entrée sur 7 jours → repli sur les 3 plus récentes
    def answer(sql, *args):
        return [] if "interval '7 days'" in sql.lower() else [_row(2)]
    fake_db.on("from gallery_items", answer)
    assert [i["id"] for i in client.get("/gallery/highlights").json()["items"]] == [2]


def test_gallery_admin_requires_admin(client, fake_db, monkeypatch):
    _session(monkeypatch, is_admin=False)
    client.cookies.set("better-auth.session_token", "t")
    assert client.patch("/admin/gallery/1", json={"hidden": True}).status_code == 403
    assert client.delete("/admin/gallery/1").status_code == 403
    client.cookies.clear()
    assert client.patch("/admin/gallery/1", json={"hidden": True}).status_code == 401


def test_gallery_admin_patch_and_delete(client, fake_db, monkeypatch, tmp_path):
    _session(monkeypatch, is_admin=True)
    import routes.gallery as gallery
    monkeypatch.setattr(gallery, "GALLERY_DIR", tmp_path)
    (tmp_path / "a.png").write_bytes(b"x")
    fake_db.on("update gallery_items", {"id": 1})
    fake_db.on("delete from gallery_items", {"file_name": "a.png"})
    client.cookies.set("better-auth.session_token", "t")
    assert client.patch("/admin/gallery/1", json={"hidden": True}).status_code == 200
    assert client.delete("/admin/gallery/1").status_code == 204
    assert not (tmp_path / "a.png").exists()
