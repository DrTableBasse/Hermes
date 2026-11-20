from fastapi import APIRouter, Request

from grades import get_grades
from limiter import limiter

router = APIRouter(tags=["grades"])


@router.get("/grades")
@limiter.limit("60/minute")
async def list_grades(request: Request):
    return {"grades": await get_grades()}
