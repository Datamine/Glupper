"""
Configuration secrets for the application.
This file should be added to .gitignore and not tracked in version control.
"""

# Database configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost/glupper"

# Redis configuration
REDIS_URL = "redis://localhost:6379/0"

# ArchiveBox configuration
ARCHIVEBOX_API_ENDPOINT = "http://localhost:8000/api/archive/"
ARCHIVEBOX_TIMEOUT = 30.0  # seconds

# JWT configuration
JWT_SECRET_KEY = "supersecretkey"  # Change this in production!
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30