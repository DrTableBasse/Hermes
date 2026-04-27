from typing import Optional
import database as db
from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel
from slugify import slugify
from auth import decode_jwt
from middleware.auth_middleware import get_current_user, require_admin, require_redacteur

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


async def _article_with_tags(article: dict) -> dict:
    tags = await db.fetch("""
        SELECT t.* FROM tags t
        JOIN article_tags at ON t.id = at.tag_id
        WHERE at.article_id = $1
    """, article['id'])
    author = await db.fetchrow(
        "SELECT user_id, username, discord_avatar FROM user_voice_data WHERE user_id = $1",
        article['author_id']
    )
    return {**article, "tags": tags, "author": author}


@router.get("")
async def list_articles(page: int = 1, limit: int = 12, tag: Optional[str] = None):
    offset = (page - 1) * limit
    if tag:
        rows = await db.fetch("""
            SELECT DISTINCT a.* FROM articles a
            JOIN article_tags at ON a.id = at.article_id
            JOIN tags t ON t.id = at.tag_id
            WHERE a.published = TRUE AND t.slug = $1
            ORDER BY a.created_at DESC LIMIT $2 OFFSET $3
        """, tag, limit, offset)
        total = await db.fetchval("""
            SELECT COUNT(DISTINCT a.id) FROM articles a
            JOIN article_tags at ON a.id = at.article_id
            JOIN tags t ON t.id = at.tag_id
            WHERE a.published = TRUE AND t.slug = $1
        """, tag)
    else:
        rows  = await db.fetch(
            "SELECT * FROM articles WHERE published = TRUE ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset
        )
        total = await db.fetchval("SELECT COUNT(*) FROM articles WHERE published = TRUE")

    articles = [await _article_with_tags(r) for r in rows]
    return {"articles": articles, "total": int(total or 0), "page": page, "limit": limit}


@router.get("/{slug}")
async def get_article(slug: str):
    article = await db.fetchrow("SELECT * FROM articles WHERE slug = $1", slug)
    if not article:
        raise HTTPException(status_code=404, detail="Article introuvable")
    if not article['published']:
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

    fields, values, i = [], [], 1
    for col in ('title', 'content', 'cover_image_url', 'published'):
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
