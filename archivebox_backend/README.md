# ArchiveBox Backend for Glupper

This directory contains the backend service for archiving URLs with ArchiveBox. It's designed to run on a separate server from the main Glupper application.

## Architecture

The ArchiveBox backend is responsible for:

1. Polling an AWS SQS queue for archive jobs
2. Processing these jobs by archiving URLs using ArchiveBox
3. Uploading the archived content to AWS S3
4. Adding a completion marker to indicate the archive is done

This architecture allows resource-intensive archiving to be offloaded from the main application server, with S3 serving as the source of truth for archive status.

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│            │    │            │    │            │    │            │
│   Glupper  │───►│  AWS SQS   │───►│ ArchiveBox │───►│   AWS S3   │
│   Server   │    │   Queue    │    │   Server   │    │            │
│            │    │            │    │            │    │            │
└────────────┘    └────────────┘    └────────────┘    └────────────┘
       ▲                                                    │
       │                                                    │
       └────────────────────────────────────────────────────┘
                   Direct check for archive status
```

## Key Features

- **No shared database** - S3 is the source of truth for archive completion
- **UUID-based file paths** - Glupper server pre-generates UUIDs for archives
- **Completion markers** - Special files in S3 indicate when archives are complete
- **Automatic cleanup** - Separate worker handles deletion requests

## Setup

### 1. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# ArchiveBox
docker run -d --name archivebox \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=yourpassword \
  -p 8000:8000 \
  -v ~/archivebox/data:/data \
  archivebox/archivebox server 0.0.0.0:8000
```

### 2. Configure

Edit `config.py` with your AWS credentials and ArchiveBox settings:

```python
# AWS Configuration
AWS_ACCESS_KEY_ID = "your-access-key"
AWS_SECRET_ACCESS_KEY = "your-secret-key"
AWS_REGION = "us-east-1"

# SQS Configuration
ARCHIVE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/glupper-archive-queue"

# S3 Configuration
ARCHIVE_S3_BUCKET = "glupper-archives"
ARCHIVE_S3_PREFIX = "archives/"
ARCHIVE_COMPLETE_MARKER = "complete.json"  # File indicating archive completion

# ArchiveBox Configuration
ARCHIVEBOX_API_ENDPOINT = "http://localhost:8000/api/archive/"
```

### 3. Run the Workers

Main archiving worker:
```bash
python worker.py
```

Cleanup worker (optional):
```bash
python cleanup.py
```

## Message Format

### Archive Job Message

```json
{
  "url": "https://example.com",
  "archive_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Example Page"
}
```

### Deletion Message

```json
{
  "archive_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## S3 Structure

For each archive:

```
s3://glupper-archives/archives/{archive_id}/
  - index.html
  - screenshot.png
  - ... other archive files ...
  - archive.zip (contains all files)
  - complete.json (indicates completion)
```

The `complete.json` file contains metadata about the archive:

```json
{
  "archive_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "timestamp": "2023-03-11T12:34:56.789Z",
  "url": "https://example.com",
  "files": [
    {"filename": "index.html", "url": "s3://...", "content_type": "text/html"},
    {"filename": "screenshot.png", "url": "s3://...", "content_type": "image/png"},
    {"filename": "archive.zip", "url": "s3://...", "content_type": "application/zip"}
  ],
  "main_file": "index.html"
}
```

## Production Deployment

For production deployment, it's recommended to:

1. Set up systemd services to ensure the workers run continuously
2. Configure logging to a file or centralized logging service
3. Set up monitoring to alert on worker failures