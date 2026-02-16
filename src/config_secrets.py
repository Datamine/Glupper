"""
Configuration secrets for the application.
This file should be added to .gitignore and not tracked in version control.
"""

# Database configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost/glupper"

# Redis configuration
REDIS_URL = "redis://localhost:6379/0"

# JWT configuration
JWT_SECRET_KEY = "supersecretkey"  # Change this in production.
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Admin key for bootstrap and moderation endpoints
ADMIN_BOOTSTRAP_KEY = "change-me-admin-key"

# Recovery/risk controls
RECOVERY_COOLDOWN_HOURS = 72
RECOVERY_SPONSOR_MIN_TRUST_DAYS = 30
RECOVERY_SPONSOR_MAX_DEMERITS = 0
