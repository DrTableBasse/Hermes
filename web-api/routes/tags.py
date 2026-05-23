from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from slugify import slugify
from middleware.auth_middleware import get_current_user, require_admin, require_redacteur
import database as db

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCreate(BaseModel):
    name:  str
    color: str = "#3b82f6"


class TagUpdate(BaseModel):
    name:  Optional[str] = None
    color: Optional[str] = None


@router.get("")
async def list_tags():
    rows = await db.fetch("SELECT * FROM tags ORDER BY name")
    return {"tags": rows}


@router.post("", status_code=201)
async def create_tag(body: TagCreate, user: dict = Depends(get_current_user)):
    require_redacteur(user)
    slug = slugify(body.name)
    tag_id = await db.fetchval(
        "INSERT INTO tags (name, slug, color) VALUES ($1, $2, $3) RETURNING id",
        body.name, slug, body.color
    )
    return await db.fetchrow("SELECT * FROM tags WHERE id = $1", tag_id)


@router.put("/{tag_id}")
async def update_tag(tag_id: int, body: TagUpdate, user: dict = Depends(get_current_user)):
    require_redacteur(user)
    tag = await db.fetchrow("SELECT * FROM tags WHERE id = $1", tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag introuvable")
    fields, values, i = [], [], 1
    if body.name is not None:
        fields.append(f"name = ${i}"); values.append(body.name); i += 1
        fields.append(f"slug = ${i}"); values.append(slugify(body.name)); i += 1
    if body.color is not None:
        fields.append(f"color = ${i}"); values.append(body.color); i += 1
    if fields:
        values.append(tag_id)
        await db.execute(f"UPDATE tags SET {', '.join(fields)} WHERE id = ${i}", *values)
    return await db.fetchrow("SELECT * FROM tags WHERE id = $1", tag_id)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(tag_id: int, user: dict = Depends(get_current_user)):
    require_redacteur(user)
    await db.execute("DELETE FROM tags WHERE id = $1", tag_id)
