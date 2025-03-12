# ArchiveBox Integration for Glupper with AWS

This document explains the distributed architecture for ArchiveBox integration using AWS services.

## Architecture Overview

The architecture separates the Glupper web server from the ArchiveBox archiving tasks:

1. **Glupper Server**: Handles all user-facing API requests and generates archive IDs
2. **AWS SQS Queue**: Decouples archiving requests for asynchronous processing
3. **ArchiveBox Server**: Dedicated server for CPU/memory-intensive archiving tasks
4. **AWS S3**: Stores all archived content and serves as the source of truth for archive status

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

## Key Benefits

- **Decoupled Services**: Main app and archiving run independently
- **No Shared Database**: S3 serves as the source of truth
- **Scalable**: Each component can scale independently
- **UUID-Based Organization**: Consistent identifiers throughout the system
- **Completion Markers**: Clear indication of archive status in S3

## Setup Instructions

### 1. AWS Configuration

#### SQS Queue Setup
```bash
# Create SQS queue for archiving jobs
aws sqs create-queue --queue-name glupper-archive-queue \
  --attributes "{\"VisibilityTimeout\":\"900\", \"MessageRetentionPeriod\":\"86400\"}"

# Create queue for deletion jobs
aws sqs create-queue --queue-name glupper-archive-delete-queue
```

#### S3 Bucket Setup
```bash
# Create S3 bucket for archives
aws s3 mb s3://glupper-archives

# Set lifecycle policy (optional, to delete old archives)
aws s3api put-bucket-lifecycle-configuration \
  --bucket glupper-archives \
  --lifecycle-configuration file://lifecycle-config.json
```

### 2. Glupper Server Configuration

Update `src/services/archive_service.py` to generate UUIDs for archives and queue them to SQS instead of directly calling ArchiveBox.

To check if an archive exists, query S3 for the completion marker file:
```python
s3_client.head_object(
    Bucket="glupper-archives",
    Key=f"archives/{archive_id}/complete.json"
)
```

### 3. ArchiveBox Backend Setup

See the `archivebox_backend` directory for detailed setup instructions. In summary:

1. Install dependencies:
```bash
cd archivebox_backend
pip install -r requirements.txt
```

2. Configure AWS credentials and endpoints in `config.py`

3. Run the worker:
```bash
python worker.py
```

## Message Formats

### Archive Job Message (Glupper → SQS → ArchiveBox)
```json
{
  "url": "https://example.com",
  "archive_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Example Page Title"
}
```

### Deletion Message (Glupper → SQS → ArchiveBox)
```json
{
  "archive_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## S3 Structure

Each archive is stored in its own directory in S3:

```
s3://glupper-archives/archives/{archive_id}/
  - index.html
  - screenshot.png
  - ... other archive files ...
  - archive.zip (contains all files)
  - complete.json (indicates completion)
```

The `complete.json` file contains metadata and serves as a marker that the archive is complete:

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

## Glupper API Integration

When a user creates a post with a URL:

1. Generate a UUID for the archive
2. Queue a message to SQS with the URL and archive_id
3. Return the post to the user with archive_id and status "pending"

To check archive status:
1. Look for `complete.json` in S3 at the archive's location
2. If found, archive is complete; if not, it's still pending

When showing an archived URL to users:
1. Generate a presigned URL to the archived content in S3
2. Or redirect to a URL serving the archived content