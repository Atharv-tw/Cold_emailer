"""FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import engine
from .routers import auth, health, profile, resumes
from .settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    missing = [
        name
        for name, value in (
            ("MASTER_KEY", settings.master_key),
            ("SESSION_SECRET", settings.session_secret),
            ("RECIPIENT_GUARD_SECRET", settings.recipient_guard_secret),
        )
        if not value
    ]
    if missing:
        # Loud on startup rather than at the first send. A service that boots
        # happily without a master key is a service that will one day be asked
        # to store a refresh token it cannot encrypt.
        logger.warning("not configured: %s - sending will refuse to run", ", ".join(missing))
    yield
    await engine.dispose()


app = FastAPI(
    title="Cold outreach API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(resumes.router)
