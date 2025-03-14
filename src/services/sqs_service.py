import json
import logging
import uuid
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from src.config_secrets import (
    ARCHIVE_DEAD_LETTER_QUEUE_URL,
    ARCHIVE_QUEUE_URL,
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
)

logger = logging.getLogger(__name__)

# Initialize SQS client
sqs_client = boto3.client(
    "sqs",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def send_archive_job_to_queue(
    job_id: str,
    url: str,
    post_id: str,
    title: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Send a message to the SQS queue for archiving a URL

    Args:
        job_id: Unique identifier for this archive job
        url: The URL to archive
        post_id: The post ID that this URL belongs to
        title: Optional title for the archived page

    Returns:
        The SQS response if successful, None otherwise
    """
    try:
        message_body = {
            "job_id": job_id,
            "url": url,
            "post_id": post_id,
            "title": title or "",
            "timestamp": json.dumps(
                {"__datetime__": True, "value": str(uuid.uuid4())},
            ),  # Use UUID as a unique timestamp marker
        }

        response = sqs_client.send_message(
            QueueUrl=ARCHIVE_QUEUE_URL,
            MessageBody=json.dumps(message_body),
            MessageAttributes={
                "JobType": {
                    "DataType": "String",
                    "StringValue": "archive",
                },
                "JobId": {
                    "DataType": "String",
                    "StringValue": job_id,
                },
                "PostId": {
                    "DataType": "String",
                    "StringValue": post_id,
                },
            },
            MessageGroupId="archive_jobs",  # For FIFO queues
            MessageDeduplicationId=job_id,  # For FIFO queues
        )

        logger.info(f"Sent archive job {job_id} to queue for URL: {url}, post: {post_id}")
    except ClientError:
        logger.exception("Failed to send archive job to queue.")
        return None
    else:
        return response


def send_delete_job_to_queue(job_id: str) -> Optional[dict[str, Any]]:
    """
    Send a message to the SQS queue to delete an archive

    Args:
        job_id: Unique identifier for the archive job to delete

    Returns:
        The SQS response if successful, None otherwise
    """
    try:
        message_body = {
            "archive_id": job_id,
            "timestamp": json.dumps(
                {"__datetime__": True, "value": str(uuid.uuid4())},
            ),
        }

        response = sqs_client.send_message(
            QueueUrl=ARCHIVE_DEAD_LETTER_QUEUE_URL,
            MessageBody=json.dumps(message_body),
            MessageAttributes={
                "JobType": {
                    "DataType": "String",
                    "StringValue": "delete",
                },
                "JobId": {
                    "DataType": "String",
                    "StringValue": job_id,
                },
            },
            MessageGroupId="delete_jobs",  # For FIFO queues
            MessageDeduplicationId=f"delete-{job_id}",  # For FIFO queues
        )

        logger.info(f"Sent delete job for archive {job_id} to queue")
    except ClientError:
        logger.exception("Failed to send delete job to queue.")
        return None
    else:
        return response
