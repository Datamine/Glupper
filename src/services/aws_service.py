"""
AWS services for Glupper.

This module handles interactions with AWS services like S3 and SQS.
"""
import json
import logging
import uuid
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from src.config_secrets import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    ARCHIVE_QUEUE_URL,
    ARCHIVE_DEAD_LETTER_QUEUE_URL,
    ARCHIVE_S3_BUCKET,
    ARCHIVE_S3_PREFIX,
)

logger = logging.getLogger(__name__)

# Initialize AWS clients
try:
    sqs_client = boto3.client(
        "sqs",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    
    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
except Exception as e:
    logger.error(f"Failed to initialize AWS clients: {e}")
    sqs_client = None
    s3_client = None


def get_s3_key(archive_id: Union[UUID, str], filename: str) -> str:
    """
    Generate an S3 key for an archived file.
    
    Args:
        archive_id: The archive ID (UUID)
        filename: The name of the file
        
    Returns:
        The S3 key
    """
    return f"{ARCHIVE_S3_PREFIX}{archive_id}/{filename}"


def check_archive_exists(archive_id: Union[UUID, str]) -> bool:
    """
    Check if an archive exists by looking for the completion marker in S3.
    
    Args:
        archive_id: The archive ID (UUID)
        
    Returns:
        True if the archive exists and is complete, False otherwise
    """
    if not s3_client:
        logger.error("S3 client not initialized")
        return False
        
    try:
        # Check for the completion marker file
        key = get_s3_key(archive_id, "complete.json")
        s3_client.head_object(
            Bucket=ARCHIVE_S3_BUCKET,
            Key=key
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            # Not found, archive doesn't exist or is incomplete
            return False
        logger.error(f"Error checking archive existence: {str(e)}")
        return False


def get_archive_metadata(archive_id: Union[UUID, str]) -> Optional[Dict]:
    """
    Get metadata for an archive from S3.
    
    Args:
        archive_id: The archive ID (UUID)
        
    Returns:
        Dictionary with archive metadata if found, None otherwise
    """
    if not s3_client:
        logger.error("S3 client not initialized")
        return None
        
    try:
        key = get_s3_key(archive_id, "complete.json")
        response = s3_client.get_object(
            Bucket=ARCHIVE_S3_BUCKET,
            Key=key
        )
        
        metadata_json = response["Body"].read().decode("utf-8")
        return json.loads(metadata_json)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            logger.info(f"Archive metadata not found for {archive_id}")
        else:
            logger.error(f"Error getting archive metadata: {str(e)}")
        return None
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
    if not s3_client:
        logger.error("S3 client not initialized")
        return None
        
    try:
        key = get_s3_key(archive_id, filename)
        response = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": ARCHIVE_S3_BUCKET,
                "Key": key,
            },
            ExpiresIn=expiration,
        )
        
        return response
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None


def queue_url_for_archiving(url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Queue a URL for archiving by sending a message to SQS.
    
    Args:
        url: The URL to archive
        title: Optional title for the page
        
    Returns:
        The archive_id (UUID) if successful, None otherwise
    """
    if not sqs_client:
        logger.error("SQS client not initialized")
        return None
        
    try:
        # Generate a unique ID for this archive
        archive_id = str(uuid.uuid4())
        
        # Prepare the message
        message = {
            "url": url,
            "archive_id": archive_id,
            "title": title or "",
        }
        
        # Send the message to SQS
        response = sqs_client.send_message(
            QueueUrl=ARCHIVE_QUEUE_URL,
            MessageBody=json.dumps(message),
        )
        
        if response.get("MessageId"):
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