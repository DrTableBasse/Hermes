from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from media_files import MediaFiles
import os
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from limiter import limiter
from json_response import SnowflakeJSONResponse
from dotenv import load_dotenv

load_dotenv()

import database as db
from routes import auth, users, leaderboard, articles, tags, media, admin, audit, access, roles
from routes import xp, notifications, endorsements, activity, quests, comments, tickets, settings, grades, live, events, hermes, gallery, staff, content, achievements


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    yield
    await db.close_pool()


# Documentation OpenAPI désactivée (constat M5) : la carte de l'API interne n'est jamais servie,
# ni sur le réseau Docker ni via le proxy Next (/api/proxy/docs, /api/proxy/openapi.json).
app = FastAPI(
    title="Hermes Web API",
    lifespan=lifespan,
    default_response_class=SnowflakeJSONResponse,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

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
app.include_router(audit.router)
app.include_router(access.router)
app.include_router(roles.router)
app.include_router(xp.router)
app.include_router(notifications.router)
app.include_router(endorsements.router)
app.include_router(activity.router)
app.include_router(quests.router)
app.include_router(comments.router)
app.include_router(tickets.router)
app.include_router(settings.router)
app.include_router(grades.router)
app.include_router(live.router)
app.include_router(events.router)
app.include_router(hermes.router)
app.include_router(gallery.router)
app.include_router(staff.router)
app.include_router(content.router)
app.include_router(achievements.router)
app.mount("/media", MediaFiles(directory="/app/media"), name="media")


@app.get("/health")
async def health():
    return {"status": "ok"}
