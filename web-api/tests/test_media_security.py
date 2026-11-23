"""Médias : envoi plafonné en flux, PDF en pièce jointe, dossiers et galerie masquée (M6, M7)."""
import pytest

from middleware import auth_middleware
from routes import media

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def _fresh():
    from limiter import limiter
    limiter.reset()


@pytest.fixture
def media_dir(client, tmp_path, monkeypatch):
    import main

    (tmp_path / "gallery").mkdir()
    (tmp_path / "gallery" / "visible.png").write_bytes(PNG)
    (tmp_path / "gallery" / "cachee.png").write_bytes(PNG)
    (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4 test")
    (tmp_path / "img.png").write_bytes(PNG)
    mount = next(r for r in main.app.routes if getattr(r, "name", None) == "media")
    monkeypatch.setattr(mount.app, "directory", str(tmp_path))
    monkeypatch.setattr(mount.app, "all_directories", [str(tmp_path)])
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path)
    return tmp_path


def _session(monkeypatch, client, *, is_admin=False, redacteur=False):
    async def fake_session(token):
        return {"sub": "5", "is_admin": is_admin, "is_redacteur": redacteur}

    monkeypatch.setattr(auth_middleware, "_fetch_session", fake_session)
    client.cookies.set("better-auth.session_token", "tok")


def _hidden_rule(fake_db):
    fake_db.on("FROM gallery_items WHERE file_name", lambda sql, name: name == "cachee.png")


# ── M6 : lecture ─────────────────────────────────────────────────────────────

def test_pdf_servi_en_piece_jointe(client, fake_db, media_dir):
    r = client.get("/media/doc.pdf")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == "attachment"
    assert "content-disposition" not in client.get("/media/img.png").headers


def test_dossier_repond_404(client, fake_db, media_dir):
    assert client.get("/media/gallery").status_code == 404
    assert client.get("/media/gallery/").status_code == 404


# ── M7 : galerie masquée ─────────────────────────────────────────────────────

def test_element_masque_non_servi_au_public(client, fake_db, media_dir):
    _hidden_rule(fake_db)
    assert client.get("/media/gallery/visible.png").status_code == 200
    assert client.get("/media/gallery/cachee.png").status_code == 404


def test_element_masque_non_servi_a_un_membre(client, fake_db, media_dir, monkeypatch):
    _hidden_rule(fake_db)
    _session(monkeypatch, client)
    assert client.get("/media/gallery/cachee.png").status_code == 404


def test_element_masque_visible_par_un_admin(client, fake_db, media_dir, monkeypatch):
    _hidden_rule(fake_db)
    _session(monkeypatch, client, is_admin=True)
    assert client.get("/media/gallery/cachee.png").status_code == 200


# ── M6 : envoi ───────────────────────────────────────────────────────────────

def test_envoi_valide(client, fake_db, media_dir, monkeypatch):
    _session(monkeypatch, client, redacteur=True)
    r = client.post("/media/upload", files={"file": ("a.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    assert (media_dir / r.json()["filename"]).read_bytes() == PNG


def test_envoi_refuse_sur_content_length_avant_lecture(client, fake_db, media_dir, monkeypatch):
    _session(monkeypatch, client, redacteur=True)
    r = client.post("/media/upload", content=b"x",
                    headers={"content-type": "multipart/form-data; boundary=b",
                             "content-length": str(media.MAX_BODY + 1)})
    assert r.status_code == 413


def test_envoi_trop_gros_refuse_en_flux(client, fake_db, media_dir, monkeypatch):
    _session(monkeypatch, client, redacteur=True)
    monkeypatch.setattr(media, "MAX_SIZE", 1024)
    monkeypatch.setattr(media, "MAX_BODY", 4096)
    big = PNG + b"\x00" * 10_000
    r = client.post("/media/upload", files={"file": ("a.png", big, "image/png")})
    assert r.status_code == 413
    assert [p for p in media_dir.iterdir() if p.is_file() and p.name not in ("doc.pdf", "img.png")] == []


def test_fichier_au_dela_de_max_size_refuse(client, fake_db, media_dir, monkeypatch):
    _session(monkeypatch, client, redacteur=True)
    monkeypatch.setattr(media, "MAX_SIZE", 1024)
    r = client.post("/media/upload", files={"file": ("a.png", PNG + b"\x00" * 2000, "image/png")})
    assert r.status_code == 413


def test_signature_mp4_exige_ftyp():
    assert media._detect_mime(b"\x00\x00\x00\x18ftypmp42") == "video/mp4"
    assert media._detect_mime(b"\x00\x00\x00\x18<html>") == "application/octet-stream"


def test_envoi_reserve_aux_redacteurs(client, fake_db, media_dir, monkeypatch):
    _session(monkeypatch, client)
    r = client.post("/media/upload", files={"file": ("a.png", PNG, "image/png")})
    assert r.status_code == 403
