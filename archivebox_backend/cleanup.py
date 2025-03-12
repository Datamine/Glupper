#!/usr/bin/env python3
"""
Cleanup script for deleting archives from S3 when posts are deleted.

This script checks for deletion messages in a separate SQS queue
and deletes the corresponding archives from S3.
"""

import json
import logging
import sys
import time
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    ARCHIVE_DEAD_LETTER_QUEUE_URL,
    POLL_INTERVAL,
)
from s3_util import delete_archive_files

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("archivebox_cleanup")

# Initialize SQS client
sqs_client = boto3.client(
    "sqs",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def process_deletion_message(message):
    """Process a deletion message from the SQS queue"""
    try:
        # Parse the message body
        body = json.loads(message["Body"])
        archive_id = body.get("archive_id")
        
        if not archive_id:
            logger.error(f"Invalid deletion message format: {body}")
            return True  # Mark as processed to remove from queue
            
        logger.info(f"Processing deletion for archive {archive_id}")
        
        # Delete the archive files from S3
        success = delete_archive_files(archive_id)
        
        if success:
            logger.info(f"Successfully deleted archive files for {archive_id}")
        else:
            logger.error(f"Failed to delete archive files for {archive_id}")
            
        # We consider the message processed even if deletion failed
        # so it doesn't stay in the queue
        return True
    except Exception as e:
        logger.error(f"Error processing deletion message: {e}")
        return False


def poll_deletion_queue():
    """Poll the SQS deletion queue"""
    while True:
        try:
            # Receive message from SQS queue
            response = sqs_client.receive_message(
                QueueUrl=ARCHIVE_DEAD_LETTER_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
                MessageAttributeNames=["All"],
            )
            
            messages = response.get("Messages", [])
            if not messages:
                # No messages, sleep before polling again
                time.sleep(POLL_INTERVAL)
                continue
                
            # Process each message
            for message in messages:
                receipt_handle = message["ReceiptHandle"]
                
                # Process the message
                success = process_deletion_message(message)
                
                # Delete the message from the queue if processed successfully
                if success:
                    sqs_client.delete_message(
                        QueueUrl=ARCHIVE_DEAD_LETTER_QUEUE_URL,
                        ReceiptHandle=receipt_handle,
                    )
                
        except KeyboardInterrupt:
            logger.info("Stopping cleanup worker")
            break
        except Exception as e:
            logger.error(f"Error polling deletion queue: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    logger.info("Starting ArchiveBox cleanup worker")
    poll_deletion_queue()