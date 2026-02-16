from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import auth, invites, moderation, social_accounts, users
from src.core.cache import close_cache, init_cache
from src.core.db import close_db, init_db

app = FastAPI(
    title="Glupper API",
    description="Invite/vouch trust graph backend for proving real humans.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(invites.router)
app.include_router(social_accounts.router)
app.include_router(moderation.router)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize database and cache clients."""
    await init_db()
    await init_cache()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Close database and cache clients."""
    await close_db()
    await close_cache()


@app.get("/health", status_code=200)
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}
