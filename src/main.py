from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import archives, auth, feed, messages, posts, users
from src.core.cache import close_cache, init_cache
from src.core.db import close_db, init_db

# Create FastAPI application
app = FastAPI(
    title="Glupper API",
    description="High-performance Twitter-like API",
    version="0.1.0",
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
app.include_router(archives.router)
app.include_router(messages.router)


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    import logging
    
    # Setup better logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Initialize database
    logging.info("Initializing database connection...")
    db_pool = await init_db()
    if db_pool is None:
        logging.error("Failed to initialize database connection! Check PostgreSQL is running and credentials are correct.")
        # We don't raise an exception here to allow the app to start, but services requiring DB will fail
    else:
        logging.info("Database connection pool initialized successfully")
    
    # Initialize cache
    logging.info("Initializing cache connection...")
    try:
        await init_cache()
        logging.info("Cache connection initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize cache connection: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown"""
    await close_db()
    await close_cache()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/version")
async def api_version():
    """API version information"""
    return {
        "version": "1.0.0",
        "name": "Glupper API",
        "endpoints": "/api/v1",
    }
