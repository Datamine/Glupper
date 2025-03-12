"""
AWS services for Glupper.

This module handles interactions with AWS services like S3 and SQS.
This service acts as a facade over the specialized s3_service and sqs_service modules.
"""
import json
import logging
import uuid
from typing import Dict, Optional, Union
from uuid import UUID

from src.config_secrets import ARCHIVE_DEAD_LETTER_QUEUE_URL
from src.services.s3_service import (
    check_archive_exists as s3_check_archive_exists,
    get_archive_from_s3,
    generate_presigned_url as s3_generate_presigned_url,
)
from src.services.sqs_service import send_archive_job_to_queue

logger = logging.getLogger(__name__)


def get_s3_key(archive_id: Union[UUID, str], filename: str) -> str:
    """
    Alias for s3_service.get_archive_s3_key for backward compatibility.
    
    Args:
        archive_id: The archive ID (UUID)
        filename: The name of the file
        
    Returns:
        The S3 key
    """
    from src.services.s3_service import get_archive_s3_key
    return get_archive_s3_key(str(archive_id), filename)


def check_archive_exists(archive_id: Union[UUID, str]) -> bool:
    """
    Check if an archive exists by looking for the completion marker in S3.
    
    Args:
        archive_id: The archive ID (UUID)
        
    Returns:
        True if the archive exists and is complete, False otherwise
    """
    return s3_check_archive_exists(str(archive_id), "complete.json")


def get_archive_metadata(archive_id: Union[UUID, str]) -> Optional[Dict]:
    """
    Get metadata for an archive from S3.
    
    Args:
        archive_id: The archive ID (UUID)
        
    Returns:
        Dictionary with archive metadata if found, None otherwise
    """
    data = get_archive_from_s3(str(archive_id), "complete.json")
    if data:
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            logger.error(f"Error parsing archive metadata: {str(e)}")
    return None


def generate_presigned_url(archive_id: Union[UUID, str], filename: str, expiration: int = 3600) -> Optional[str]:
    """
    Generate a presigned URL for accessing an archived file.
    
    Args:
        archive_id: The archive ID (UUID)
        filename: The name of the file to access
        expiration: URL expiration time in seconds
        
    Returns:
        Presigned URL if successful, None otherwise
    """
    return s3_generate_presigned_url(str(archive_id), filename, expiration)


def queue_url_for_archiving(url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Queue a URL for archiving by sending a message to SQS.
    
    Args:
        url: The URL to archive
        title: Optional title for the page
        
    Returns:
        The archive_id (UUID) if successful, None otherwise
    """
    try:
        # Generate a unique ID for this archive
        archive_id = str(uuid.uuid4())
        
        # Use a placeholder post_id when called directly from this service
        # The actual post_id association happens in archive_service.py
        post_id = "pending"
        
        # Send to queue using specialized service
        response = send_archive_job_to_queue(archive_id, url, post_id, title)
        
        if response:
            logger.info(f"Queued URL {url} for archiving with ID {archive_id}")
            return archive_id
        else:
            logger.error(f"Failed to queue URL {url} for archiving")
            return None
    except Exception as e:
        logger.error(f"Error queuing URL for archiving: {str(e)}")
        return None


def queue_archive_for_deletion(archive_id: Union[UUID, str]) -> bool:
    """
    Queue an archive for deletion by sending a message to SQS.
    
    Args:
        archive_id: The archive ID (UUID) to delete
        
    Returns:
        True if successful, False otherwise
    """
    from src.services.sqs_service import sqs_client
    
    if not sqs_client:
        logger.error("SQS client not initialized")
        return False
        
    try:
        # Prepare the message
        message = {
            "archive_id": str(archive_id),
        }
        
        # Send the message to SQS
        response = sqs_client.send_message(
            QueueUrl=ARCHIVE_DEAD_LETTER_QUEUE_URL,
            MessageBody=json.dumps(message),
        )
        
        if response.get("MessageId"):
            logger.info(f"Queued archive {archive_id} for deletion")
            return True
        else:
            logger.error(f"Failed to queue archive {archive_id} for deletion")
            return False
    except Exception as e:
        logger.error(f"Error queuing archive for deletion: {str(e)}")
        return False