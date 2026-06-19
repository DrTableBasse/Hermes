from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from limiter import limiter
from dotenv import load_dotenv

load_dotenv()

import database as db
from routes import auth, users, leaderboard, articles, tags, media, admin
from routes import xp, notifications, endorsements, activity, quests, comments, automod_api, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    yield
    await db.close_pool()


app = FastAPI(title="Hermes Web API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://web:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cookie"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(leaderboard.router)
app.include_router(articles.router)
app.include_router(tags.router)
app.include_router(media.router)
app.include_router(admin.router)
app.include_router(xp.router)
app.include_router(notifications.router)
app.include_router(endorsements.router)
app.include_router(activity.router)
app.include_router(quests.router)
app.include_router(comments.router)
app.include_router(automod_api.router)
app.include_router(tickets.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
