import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from glupper.app.api import auth, users, posts, feed
from glupper.app.core.db import init_db, close_db
from glupper.app.core.cache import init_cache, close_cache

# Create FastAPI application
app = FastAPI(
    title="Glupper API",
    description="High-performance Twitter-like API",
    version="0.1.0"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(feed.router)

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    await init_db()
    await init_cache()
    
@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown"""
    await close_db()
    await close_cache()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}