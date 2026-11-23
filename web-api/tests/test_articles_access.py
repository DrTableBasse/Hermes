"""Articles : rôle rédacteur exigé pour modifier/supprimer (M3) ; commentaires des brouillons (M8)."""
import pytest

from middleware import auth_middleware

ARTICLE = {"id": 9, "author_id": 5, "published": False, "title": "t", "slug": "t", "content": "c",
           "cover_image_url": None}


@pytest.fixture(autouse=True)
def _fresh():
    from limiter import limiter
    limiter.reset()


@pytest.fixture
def as_user(client, monkeypatch):
    def _as(sub="5", *, is_admin=False, redacteur=False):
        async def fake_session(token):
            return {"sub": sub, "is_admin": is_admin, "is_redacteur": redacteur,
                "permissions": frozenset({"articles.write", "articles.publish"} if redacteur else ())}

        monkeypatch.setattr(auth_middleware, "_fetch_session", fake_session)
        client.cookies.set("better-auth.session_token", "tok")
    return _as


def _writes(fake_db):
    return [c for c in fake_db.calls if c[0] == "execute"]


# ── M3 ───────────────────────────────────────────────────────────────────────

def test_auteur_sans_role_redacteur_ne_peut_ni_publier_ni_supprimer(client, fake_db, as_user):
    fake_db.on("FROM articles WHERE id", ARTICLE)
    as_user("5")
    assert client.put("/articles/9", json={"published": True}).status_code == 403
    assert client.delete("/articles/9").status_code == 403
    assert _writes(fake_db) == []


def test_auteur_redacteur_peut_modifier_et_supprimer(client, fake_db, as_user):
    fake_db.on("FROM articles WHERE id", ARTICLE)
    as_user("5", redacteur=True)
    assert client.put("/articles/9", json={"title": "u"}).status_code == 200
    assert client.delete("/articles/9").status_code == 204


def test_redacteur_non_auteur_refuse(client, fake_db, as_user):
    fake_db.on("FROM articles WHERE id", ARTICLE)
    as_user("6", redacteur=True)
    assert client.delete("/articles/9").status_code == 403


# ── M8 ───────────────────────────────────────────────────────────────────────

def _comments(fake_db, published):
    fake_db.on("SELECT author_id, published FROM articles", {"author_id": 5, "published": published})
    fake_db.on("FROM article_comments", [{"id": 1, "content": "x", "username": "u"}])


def test_commentaires_article_publie_publics(client, fake_db):
    _comments(fake_db, True)
    r = client.get("/comments/article/9")
    assert r.status_code == 200 and len(r.json()["comments"]) == 1


def test_commentaires_brouillon_caches_au_public_et_aux_membres(client, fake_db, as_user):
    _comments(fake_db, False)
    assert client.get("/comments/article/9").status_code == 404
    as_user("6")
    assert client.get("/comments/article/9").status_code == 404


@pytest.mark.parametrize("who", [
    {"sub": "5"}, {"sub": "6", "redacteur": True}, {"sub": "6", "is_admin": True},
])
def test_commentaires_brouillon_lisibles_auteur_redacteurs_admin(client, fake_db, as_user, who):
    _comments(fake_db, False)
    as_user(**who)
    assert client.get("/comments/article/9").status_code == 200


def test_commentaires_article_inexistant(client, fake_db):
    assert client.get("/comments/article/404").status_code == 404
