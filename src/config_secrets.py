"""
Configuration secrets for the application.
This file should be added to .gitignore and not tracked in version control.
"""

# Database configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost/glupper"

# Redis configuration
REDIS_URL = "redis://localhost:6379/0"

# ArchiveBox configuration
ARCHIVEBOX_API_ENDPOINT = "http://archive-server.example.com/api/archive/"
ARCHIVEBOX_TIMEOUT = 30.0  # seconds

# JWT configuration
JWT_SECRET_KEY = "supersecretkey"  # Change this in production!
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30

# AWS Configuration
AWS_ACCESS_KEY_ID = "your-access-key"
AWS_SECRET_ACCESS_KEY = "your-secret-key"
AWS_REGION = "us-east-1"

# SQS Configuration
ARCHIVE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/glupper-archive-queue"
ARCHIVE_DEAD_LETTER_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/glupper-archive-delete-queue"

# S3 Configuration
ARCHIVE_S3_BUCKET = "glupper-archives"
ARCHIVE_S3_PREFIX = "archives/"
ARCHIVE_COMPLETE_MARKER = "complete.json"  # File indicating archive completion