from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from middleware.auth_middleware import get_current_user
import database as db

router = APIRouter(prefix="/comments", tags=["comments"])


class CommentCreate(BaseModel):
    article_id: int
    content: str
    parent_id: Optional[int] = None


@router.get("/article/{article_id}")
async def get_comments(article_id: int):
    rows = await db.fetch("""
        SELECT c.*, v.username, v.discord_avatar
        FROM article_comments c
        JOIN user_voice_data v ON c.user_id = v.user_id
        WHERE c.article_id = $1
        ORDER BY c.created_at ASC
    """, article_id)
    return {"comments": [dict(r) for r in rows]}


@router.post("")
async def create_comment(body: CommentCreate, user: dict = Depends(get_current_user)):
    if not body.content.strip():
        raise HTTPException(400, "Commentaire vide")
    content = body.content.strip()[:2000]
    comment_id = await db.fetchval("""
        INSERT INTO article_comments (article_id, user_id, content, parent_id)
        VALUES ($1, $2, $3, $4) RETURNING id
    """, body.article_id, int(user['sub']), content, body.parent_id)
    row = await db.fetchrow("""
        SELECT c.*, v.username, v.discord_avatar FROM article_comments c
        JOIN user_voice_data v ON c.user_id = v.user_id WHERE c.id = $1
    """, comment_id)
    return dict(row)


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(comment_id: int, user: dict = Depends(get_current_user)):
    comment = await db.fetchrow("SELECT * FROM article_comments WHERE id=$1", comment_id)
    if not comment:
        raise HTTPException(404, "Commentaire introuvable")
    if str(comment['user_id']) != user['sub'] and not user.get('is_admin'):
        raise HTTPException(403, "Accès interdit")
    await db.execute("DELETE FROM article_comments WHERE id=$1", comment_id)


@router.post("/{comment_id}/vote")
async def vote_comment(comment_id: int, user: dict = Depends(get_current_user)):
    user_id = int(user['sub'])
    existing = await db.fetchval(
        "SELECT id FROM article_votes WHERE user_id=$1 AND comment_id=$2", user_id, comment_id
    )
    if existing:
        await db.execute("DELETE FROM article_votes WHERE id=$1", existing)
        await db.execute("UPDATE article_comments SET vote_count = vote_count - 1 WHERE id=$1", comment_id)
        return {"voted": False}
    await db.execute(
        "INSERT INTO article_votes (user_id, comment_id) VALUES ($1, $2)", user_id, comment_id
    )
    await db.execute("UPDATE article_comments SET vote_count = vote_count + 1 WHERE id=$1", comment_id)
    return {"voted": True}
