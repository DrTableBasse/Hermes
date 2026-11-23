"""/media (fichiers statiques) hors limiteur (vérification demandée par le constat C1).

L'optimiseur d'images du site lit /media/* depuis son conteneur : une seule IP pour
tous les visiteurs. SlowAPIMiddleware n'applique pas la limite par défaut (120/min) à
un montage Starlette ; ce test le fige.
"""


def test_media_is_not_rate_limited(client, tmp_path, monkeypatch):
    import main

    (tmp_path / "gallery").mkdir()
    (tmp_path / "gallery" / "a.png").write_bytes(b"PNG")
    mount = next(r for r in main.app.routes if getattr(r, "name", None) == "media")
    monkeypatch.setattr(mount.app, "directory", str(tmp_path))
    monkeypatch.setattr(mount.app, "all_directories", [str(tmp_path)])
    headers = {"x-client-ip": "198.51.100.77"}
    statuses = {client.get("/media/gallery/a.png", headers=headers).status_code
                for _ in range(130)}
    assert statuses == {200}


def test_default_limit_still_applies_to_routes(client):
    headers = {"x-client-ip": "198.51.100.78"}
    statuses = [client.get("/health", headers=headers).status_code for _ in range(125)]
    assert statuses[0] == 200 and statuses[-1] == 429
