"""Médias : envoi plafonné en flux, PDF en pièce jointe, dossiers et galerie masquée (M6, M7)."""
import pytest

from middleware import auth_middleware
from routes import media

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def _fresh():
    import media_files
    from limiter import limiter
    limiter.reset()
    media_files.invalidate_hidden_gallery()


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
    fake_db.on("FROM gallery_items WHERE hidden", [{"file_name": "cachee.png"}])


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


def _gallery_sql(fake_db):
    return [c for c in fake_db.calls if "gallery_items" in c[1]]


def test_galerie_fichier_absent_sans_requete_sql(client, fake_db, media_dir):
    """m4 : un nom inexistant (ou un dossier) répond 404 sans toucher la base."""
    _hidden_rule(fake_db)
    for path in ("/media/gallery/absent.png", "/media/gallery/x" + "a" * 40 + ".png"):
        assert client.get(path).status_code == 404
    assert _gallery_sql(fake_db) == []


def test_galerie_noms_masques_en_cache(client, fake_db, media_dir):
    """m4 : une seule requête SQL pour une rafale de lectures de la galerie."""
    _hidden_rule(fake_db)
    for _ in range(5):
        assert client.get("/media/gallery/visible.png").status_code == 200
        assert client.get("/media/gallery/cachee.png").status_code == 404
    assert len(_gallery_sql(fake_db)) == 1


def test_galerie_cache_expire_apres_ttl(client, fake_db, media_dir, monkeypatch):
    import media_files

    monkeypatch.setattr(media_files, "HIDDEN_TTL", 0.0)
    _hidden_rule(fake_db)
    client.get("/media/gallery/visible.png")
    client.get("/media/gallery/visible.png")
    assert len(_gallery_sql(fake_db)) == 2


def test_galerie_cache_invalide_par_le_patch_admin(client, fake_db, media_dir, monkeypatch):
    hidden = {"cachee.png"}
    fake_db.on("FROM gallery_items WHERE hidden",
               lambda sql: [{"file_name": n} for n in sorted(hidden)])
    fake_db.on("UPDATE gallery_items", {"id": 1})
    assert client.get("/media/gallery/visible.png").status_code == 200

    _session(monkeypatch, client, is_admin=True)
    hidden.add("visible.png")
    assert client.patch("/admin/gallery/1", json={"hidden": True}).status_code == 200
    client.cookies.clear()
    assert client.get("/media/gallery/visible.png").status_code == 404


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


CRLF = bytes([13, 10])


def _chunked_multipart(payload: bytes, *, chunk=1024):
    """Corps multipart produit par un générateur : httpx l'envoie en « chunked », sans
    Content-Length (seul `_capped_receive` peut alors borner la lecture)."""
    head = CRLF.join([
        b"--b",
        b'Content-Disposition: form-data; name="file"; filename="a.png"',
        b"Content-Type: image/png",
        b"",
        b"",
    ])
    body = head + payload + CRLF + b"--b--" + CRLF

    def gen():
        for i in range(0, len(body), chunk):
            yield body[i:i + chunk]
    return gen()


def _post_chunked(client, gen):
    return client.post("/media/upload", content=gen,
                       headers={"content-type": "multipart/form-data; boundary=b"})


def test_envoi_chunked_sous_le_plafond_accepte(client, fake_db, media_dir, monkeypatch):
    _session(monkeypatch, client, redacteur=True)
    r = _post_chunked(client, _chunked_multipart(PNG))
    assert r.status_code == 200, r.text
    assert (media_dir / r.json()["filename"]).read_bytes() == PNG


def test_envoi_chunked_borne_en_flux_sans_content_length(client, fake_db, media_dir, monkeypatch):
    """m2 : le fichier (8 Ko) reste sous MAX_SIZE ; seul le plafond de flux du corps (4 Ko)
    peut refuser. Sans `_capped_receive`, cet envoi serait accepté (200)."""
    _session(monkeypatch, client, redacteur=True)
    monkeypatch.setattr(media, "MAX_BODY", 4096)
    r = _post_chunked(client, _chunked_multipart(PNG + b"\x00" * 8192))
    assert r.status_code == 413, r.text
    assert [p for p in media_dir.iterdir() if p.is_file() and p.name not in ("doc.pdf", "img.png")] == []


def _asgi_chunks(body: bytes, chunk: int, consumed: list):
    """`receive` ASGI qui livre le corps message par message, comme uvicorn en « chunked »."""
    parts = [body[i:i + chunk] for i in range(0, len(body), chunk)]

    async def receive():
        i = len(consumed)
        consumed.append(i)
        if i < len(parts):
            return {"type": "http.request", "body": parts[i], "more_body": i + 1 < len(parts)}
        return {"type": "http.disconnect"}
    return receive, len(parts)


def test_flux_coupe_au_plafond_et_temporaires_fermes(monkeypatch):
    """m2/m3 : corps reçu en plusieurs messages, sans Content-Length. La lecture s'arrête au
    plafond (413) sans consommer la suite, et les fichiers temporaires déjà ouverts par le
    parseur multipart sont fermés."""
    import asyncio

    import starlette.formparsers as formparsers
    from fastapi import HTTPException
    from starlette.requests import Request

    opened = []

    class Spy(formparsers.SpooledTemporaryFile):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            opened.append(self)

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", Spy)
    monkeypatch.setattr(media, "MAX_BODY", 4096)
    body = b"".join(_chunked_multipart(PNG + bytes(16384)))
    consumed = []
    receive, total = _asgi_chunks(body, 1024, consumed)
    scope = {"type": "http", "method": "POST", "path": "/media/upload", "query_string": b"",
             "headers": [(b"content-type", b"multipart/form-data; boundary=b")]}

    with pytest.raises(HTTPException) as exc:
        asyncio.run(media._capped_form(Request(scope, receive)))
    assert exc.value.status_code == 413
    assert len(consumed) <= 5 < total
    assert opened, "le parseur aurait dû ouvrir un fichier temporaire avant le plafond"
    assert all(f.closed for f in opened)


def test_corps_multipart_mal_forme_400(client, fake_db, media_dir, monkeypatch):
    _session(monkeypatch, client, redacteur=True)
    r = client.post("/media/upload", content=b"x", headers={"content-type": "multipart/form-data"})
    assert r.status_code == 400


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
