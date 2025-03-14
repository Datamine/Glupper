"""
Utilities for working with AWS S3.
"""

import json
import logging
import os
from io import BytesIO
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError
from config import (
    ARCHIVE_COMPLETE_MARKER,
    ARCHIVE_S3_BUCKET,
    ARCHIVE_S3_PREFIX,
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
)

logger = logging.getLogger("s3_util")

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def get_s3_key(archive_id: str, filename: str) -> str:
    """
    Generate an S3 key for an archived file

    Args:
        archive_id: The archive ID (UUID generated by Glupper server)
        filename: The name of the file being stored

    Returns:
        The S3 key
    """
    return f"{ARCHIVE_S3_PREFIX}{archive_id}/{filename}"


def upload_file_to_s3(
    file_path: str,
    archive_id: str,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Optional[str]:
    """
    Upload a file to S3

    Args:
        file_path: The path to the file to upload
        archive_id: The archive ID
        filename: Optional filename override (defaults to basename of file_path)
        content_type: Optional content type

    Returns:
        The S3 URL if successful, None otherwise
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        actual_filename = filename or os.path.basename(file_path)
        key = get_s3_key(archive_id, actual_filename)

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        with open(file_path, "rb") as f:
            s3_client.upload_fileobj(
                f,
                ARCHIVE_S3_BUCKET,
                key,
                ExtraArgs=extra_args,
            )

        return f"s3://{ARCHIVE_S3_BUCKET}/{key}"
    except Exception as e:
        logger.error(f"Error uploading file to S3: {str(e)}")
        return None


def create_zip_archive(
    files: list[Dict],
    archive_id: str,
) -> Optional[str]:
    """
    Create a ZIP archive of files and upload to S3

    Args:
        files: List of file information dictionaries with 'path' and 'filename' keys
        archive_id: The archive ID

    Returns:
        The S3 URL of the ZIP file if successful, None otherwise
    """
    try:
        import zipfile

        # Create a ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_info in files:
                file_path = file_info["path"]
                arcname = file_info["filename"]

                if os.path.exists(file_path) and os.path.isfile(file_path):
                    zipf.write(file_path, arcname=arcname)
                else:
                    logger.warning(f"File not found for ZIP: {file_path}")

        # Reset buffer position
        zip_buffer.seek(0)

        # Upload the ZIP to S3
        key = get_s3_key(archive_id, "archive.zip")
        s3_client.upload_fileobj(
            zip_buffer,
            ARCHIVE_S3_BUCKET,
            key,
            ExtraArgs={"ContentType": "application/zip"},
        )

        # Return the S3 URL
        return f"s3://{ARCHIVE_S3_BUCKET}/{key}"
    except Exception as e:
        logger.error(f"Error creating ZIP archive: {str(e)}")
        return None


def upload_completion_marker(
    archive_id: str,
    metadata: Dict,
) -> bool:
    """
    Upload a completion marker file to indicate the archive is complete

    Args:
        archive_id: The archive ID
        metadata: Dictionary with metadata about the archive

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create a JSON file with metadata
        metadata_json = json.dumps(
            {
                "archive_id": archive_id,
                "status": "completed",
                "timestamp": metadata.get("timestamp", ""),
                "url": metadata.get("url", ""),
                "snapshot_id": metadata.get("snapshot_id", ""),
                "files": metadata.get("files", []),
                "main_file": metadata.get("main_file", "index.html"),
            },
        )

        # Upload to S3
        key = get_s3_key(archive_id, ARCHIVE_COMPLETE_MARKER)
        s3_client.put_object(
            Bucket=ARCHIVE_S3_BUCKET,
            Key=key,
            Body=metadata_json,
            ContentType="application/json",
        )

        logger.info(f"Uploaded completion marker for archive {archive_id}")
        return True
    except Exception as e:
        logger.error(f"Error uploading completion marker: {str(e)}")
        return False


def check_archive_exists(archive_id: str) -> bool:
    """
    Check if an archive exists and is complete in S3

    Args:
        archive_id: The archive ID

    Returns:
        True if archive exists and is complete, False otherwise
    """
    try:
        # Check if the completion marker exists
        key = get_s3_key(archive_id, ARCHIVE_COMPLETE_MARKER)
        s3_client.head_object(
            Bucket=ARCHIVE_S3_BUCKET,
            Key=key,
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            # Not found, archive doesn't exist or is incomplete
            return False
        logger.error(f"Error checking archive existence: {str(e)}")
        return False


def get_archive_metadata(archive_id: str) -> Optional[Dict]:
    """
    Get metadata for an archive from S3

    Args:
        archive_id: The archive ID

    Returns:
        Dictionary with metadata if successful, None otherwise
    """
    try:
        key = get_s3_key(archive_id, ARCHIVE_COMPLETE_MARKER)
        response = s3_client.get_object(
            Bucket=ARCHIVE_S3_BUCKET,
            Key=key,
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


def generate_presigned_url(archive_id: str, filename: str, expiration: int = 3600) -> Optional[str]:
    """
    Generate a presigned URL for accessing an archived file

    Args:
        archive_id: The archive ID
        filename: The name of the file
        expiration: Expiration time in seconds

    Returns:
        Presigned URL if successful, None otherwise
    """
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


def delete_archive_files(archive_id: str) -> bool:
    """
    Delete all files for an archive from S3

    Args:
        archive_id: The archive ID

    Returns:
        True if successful, False otherwise
    """
    try:
        # List all objects with the archive_id prefix
        prefix = get_s3_key(archive_id, "")
        response = s3_client.list_objects_v2(
            Bucket=ARCHIVE_S3_BUCKET,
            Prefix=prefix,
        )

        if "Contents" not in response:
            logger.warning(f"No objects found for archive {archive_id}")
            return True

        # Delete the objects
        delete_keys = {"Objects": [{"Key": obj["Key"]} for obj in response["Contents"]]}
        s3_client.delete_objects(
            Bucket=ARCHIVE_S3_BUCKET,
            Delete=delete_keys,
        )

        logger.info(f"Deleted {len(response['Contents'])} objects for archive {archive_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting archive files: {str(e)}")
        return False
