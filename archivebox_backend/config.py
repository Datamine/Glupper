"""
Configuration for the ArchiveBox backend.
These settings control the worker that archives URLs from the SQS queue.
"""

# AWS Configuration
AWS_ACCESS_KEY_ID = "your-access-key"
AWS_SECRET_ACCESS_KEY = "your-secret-key"
AWS_REGION = "us-east-1"

# SQS Configuration
ARCHIVE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/glupper-archive-queue"
ARCHIVE_DEAD_LETTER_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/glupper-archive-dlq"

# S3 Configuration
ARCHIVE_S3_BUCKET = "glupper-archives"
ARCHIVE_S3_PREFIX = "archives/"
ARCHIVE_COMPLETE_MARKER = "complete.json"  # File indicating archive completion

# ArchiveBox Configuration
ARCHIVEBOX_API_ENDPOINT = "http://localhost:8000/api/archive/"
ARCHIVEBOX_DATA_DIR = "/data"

# Worker Configuration
POLL_INTERVAL = 5  # seconds
MAX_RETRIES = 3
SQS_VISIBILITY_TIMEOUT = 300  # seconds