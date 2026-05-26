from typing import Optional
import database as db
from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel
from slugify import slugify
from middleware.auth_middleware import get_current_user, get_optional_user, require_admin, require_redacteur

router = APIRouter(prefix="/articles", tags=["articles"])


class ArticleCreate(BaseModel):
    title:           str
    content:         str
    cover_image_url: Optional[str] = None
    published:       bool = False
    tag_ids:         list[int] = []


class ArticleUpdate(BaseModel):
    title:           Optional[str] = None
    content:         Optional[str] = None
    cover_image_url: Optional[str] = None
    published:       Optional[bool] = None
    tag_ids:         Optional[list[int]] = None


async def _enrich_articles(rows: list) -> list:
    """Fetch tags and authors for a list of articles in 2 bulk queries (no N+1)."""
    if not rows:
        return []
    article_ids = [r['id'] for r in rows]
    author_ids  = list({r['author_id'] for r in rows})

    all_tags = await db.fetch("""
        SELECT t.id, t.name, t.slug, t.color, at.article_id
        FROM tags t
        JOIN article_tags at ON t.id = at.tag_id
        WHERE at.article_id = ANY($1::int[])
    """, article_ids)

    all_authors = await db.fetch("""
        SELECT user_id, username, discord_avatar
        FROM user_voice_data
        WHERE user_id = ANY($1::bigint[])
    """, author_ids)

    tags_by_article = {}
    for t in all_tags:
        tags_by_article.setdefault(t['article_id'], []).append({k: t[k] for k in ('id', 'name', 'slug', 'color')})

    authors_by_id = {a['user_id']: dict(a) for a in all_authors}

    result = []
    for r in rows:
        d = dict(r)
        d['tags']   = tags_by_article.get(r['id'], [])
        d['author'] = authors_by_id.get(r['author_id'])
        result.append(d)
    return result


async def _article_with_tags(article: dict) -> dict:
    """Single-article enrichment (used for create/update responses)."""
    enriched = await _enrich_articles([article])
    return enriched[0] if enriched else article


@router.get("/mine")
async def my_articles(user: dict = Depends(get_current_user)):
    """Returns all articles (including drafts) authored by the current user."""
    rows = await db.fetch(
        "SELECT * FROM articles WHERE author_id = $1 ORDER BY created_at DESC",
        int(user['sub'])
    )
    return {"articles": await _enrich_articles(rows)}


@router.get("")
async def list_articles(
    page: int = 1,
    limit: int = 12,
    tag: Optional[str] = None,
    search: Optional[str] = None,
):
    page  = max(1, page)
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit

    conditions = ["a.published = TRUE"]
    params: list = []
    i = 1

    if tag:
        conditions.append(f"""
            EXISTS (
                SELECT 1 FROM article_tags at2
                JOIN tags t2 ON t2.id = at2.tag_id
                WHERE at2.article_id = a.id AND t2.slug = ${i}
            )
        """)
        params.append(tag); i += 1

    if search:
        conditions.append(f"(a.title ILIKE ${i} OR a.content ILIKE ${i})")
        params.append(f"%{search}%"); i += 1

    where = "WHERE " + " AND ".join(conditions)

    rows = await db.fetch(
        f"SELECT a.* FROM articles a {where} ORDER BY a.created_at DESC LIMIT ${i} OFFSET ${i+1}",
        *params, limit, offset
    )
    total = await db.fetchval(
        f"SELECT COUNT(*) FROM articles a {where}",
        *params
    )

    articles = await _enrich_articles(rows)
    return {"articles": articles, "total": int(total or 0), "page": page, "limit": limit}


@router.get("/by-id/{article_id}")
async def get_article_by_id(article_id: int, user: Optional[dict] = Depends(get_optional_user)):
    article = await db.fetchrow("SELECT * FROM articles WHERE id = $1", article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article introuvable")
    if not article['published']:
        is_author = user and int(user['sub']) == article['author_id']
        is_admin  = user and user.get('is_admin')
        if not (is_author or is_admin):
            raise HTTPException(status_code=404, detail="Article introuvable")
    return await _article_with_tags(article)


@router.get("/{slug}")
async def get_article(slug: str, user: Optional[dict] = Depends(get_optional_user)):
    article = await db.fetchrow("SELECT * FROM articles WHERE slug = $1", slug)
    if not article:
        raise HTTPException(status_code=404, detail="Article introuvable")
    if not article['published']:
        is_author = user and int(user['sub']) == article['author_id']
        is_admin  = user and user.get('is_admin')
        if not (is_author or is_admin):
            raise HTTPException(status_code=404, detail="Article introuvable")
    return await _article_with_tags(article)


@router.post("", status_code=201)
async def create_article(body: ArticleCreate,
                          user: dict = Depends(get_current_user)):
    require_redacteur(user)
    slug = slugify(body.title)
    existing = await db.fetchval("SELECT id FROM articles WHERE slug = $1", slug)
    if existing:
        slug = f"{slug}-{int(__import__('time').time())}"

    article_id = await db.fetchval("""
        INSERT INTO articles (author_id, title, slug, content, cover_image_url, published)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
    """, int(user['sub']), body.title, slug, body.content, body.cover_image_url, body.published)

    if body.tag_ids:
        await db.executemany(
            "INSERT INTO article_tags (article_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            [(article_id, tid) for tid in body.tag_ids]
        )
    article = await db.fetchrow("SELECT * FROM articles WHERE id = $1", article_id)
    return await _article_with_tags(article)


@router.put("/{article_id}")
async def update_article(article_id: int, body: ArticleUpdate,
                          user: dict = Depends(get_current_user)):
    article = await db.fetchrow("SELECT * FROM articles WHERE id = $1", article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article introuvable")
    if str(article['author_id']) != user['sub'] and not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Accès interdit")

    # Whitelist explicite — ne jamais construire col depuis une entrée utilisateur
    ALLOWED_ARTICLE_COLS = ('title', 'content', 'cover_image_url', 'published')
    fields, values, i = [], [], 1
    for col in ALLOWED_ARTICLE_COLS:
        val = getattr(body, col)
        if val is not None:
            fields.append(f"{col} = ${i}")
            values.append(val)
            i += 1
    if fields:
        values.append(article_id)
        await db.execute(
            f"UPDATE articles SET {', '.join(fields)}, updated_at = NOW() WHERE id = ${i}",
            *values
        )

    if body.tag_ids is not None:
        await db.execute("DELETE FROM article_tags WHERE article_id = $1", article_id)
        if body.tag_ids:
            await db.executemany(
                "INSERT INTO article_tags (article_id, tag_id) VALUES ($1, $2)",
                [(article_id, tid) for tid in body.tag_ids]
            )

    updated = await db.fetchrow("SELECT * FROM articles WHERE id = $1", article_id)
    return await _article_with_tags(updated)


@router.delete("/{article_id}", status_code=204)
async def delete_article(article_id: int, user: dict = Depends(get_current_user)):
    article = await db.fetchrow("SELECT * FROM articles WHERE id = $1", article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article introuvable")
    if str(article['author_id']) != user['sub'] and not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Accès interdit")
    await db.execute("DELETE FROM articles WHERE id = $1", article_id)
