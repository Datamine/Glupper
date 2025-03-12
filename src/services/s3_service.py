import logging
from typing import BinaryIO, Optional

import boto3
from botocore.exceptions import ClientError

from src.config_secrets import (
    ARCHIVE_S3_BUCKET,
    ARCHIVE_S3_PREFIX,
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
)

logger = logging.getLogger(__name__)

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def get_archive_s3_key(job_id: str, filename: str) -> str:
    """
    Generate an S3 key for an archived file

    Args:
        job_id: The archive job ID
        filename: The name of the file being stored

    Returns:
        The S3 key
    """
    return f"{ARCHIVE_S3_PREFIX}{job_id}/{filename}"


def check_archive_exists(job_id: str, filename: str) -> bool:
    """
    Check if an archive file exists in S3

    Args:
        job_id: The archive job ID
        filename: The name of the file to check

    Returns:
        True if the file exists, False otherwise
    """
    try:
        key = get_archive_s3_key(job_id, filename)
        s3_client.head_object(
            Bucket=ARCHIVE_S3_BUCKET,
            Key=key,
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            # Not found
            return False
        logger.exception("Error checking if archive exists")
        return False


def upload_archive_to_s3(
    file_content: BinaryIO,
    job_id: str,
    filename: str,
    content_type: Optional[str] = None,
) -> Optional[str]:
    """
    Upload an archived file to S3

    Args:
        file_content: The content of the file to upload
        job_id: The archive job ID
        filename: The name of the file being stored
        content_type: The content type of the file

    Returns:
        The S3 URL if successful, None otherwise
    """
    try:
        key = get_archive_s3_key(job_id, filename)

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        s3_client.upload_fileobj(
            file_content,
            ARCHIVE_S3_BUCKET,
            key,
            ExtraArgs=extra_args,
        )
    except ClientError:
        logger.exception("Failed to upload archive to S3.")
        return None
    else:
        # Return the S3 URL
        return f"s3://{ARCHIVE_S3_BUCKET}/{key}"


def get_archive_from_s3(job_id: str, filename: str) -> Optional[bytes]:
    """
    Get an archived file from S3

    Args:
        job_id: The archive job ID
        filename: The name of the file

    Returns:
        The file content if successful, None otherwise
    """
    try:
        key = get_archive_s3_key(job_id, filename)

        response = s3_client.get_object(
            Bucket=ARCHIVE_S3_BUCKET,
            Key=key,
        )

        return response["Body"].read()
    except ClientError:
        logger.exception("Failed to get archive from S3.")
        return None


def delete_archive_from_s3(job_id: str, filename: Optional[str] = None) -> bool:
    """
    Delete an archived file or a whole job folder from S3

    Args:
        job_id: The archive job ID
        filename: Optional filename to delete. If None, deletes the entire job folder

    Returns:
        True if successful, False otherwise
    """
    try:
        if filename:
            # Delete a specific file
            key = get_archive_s3_key(job_id, filename)
            s3_client.delete_object(
                Bucket=ARCHIVE_S3_BUCKET,
                Key=key,
            )
        else:
            # Delete all files for this job
            prefix = f"{ARCHIVE_S3_PREFIX}{job_id}/"
            objects = s3_client.list_objects_v2(
                Bucket=ARCHIVE_S3_BUCKET,
                Prefix=prefix,
            )

            if "Contents" in objects:
                delete_keys = {"Objects": [{"Key": obj["Key"]} for obj in objects["Contents"]]}
                s3_client.delete_objects(
                    Bucket=ARCHIVE_S3_BUCKET,
                    Delete=delete_keys,
                )
    except ClientError:
        logger.exception("Failed to delete archive from S3.")
        return False
    else:
        return True


def generate_presigned_url(job_id: str, filename: str, expiration: int = 3600) -> Optional[str]:
    """
    Generate a presigned URL for accessing an archived file

    Args:
        job_id: The archive job ID
        filename: The name of the file
        expiration: Expiration time in seconds

    Returns:
        Presigned URL if successful, None otherwise
    """
    try:
        key = get_archive_s3_key(job_id, filename)

        return s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": ARCHIVE_S3_BUCKET,
                "Key": key,
            },
            ExpiresIn=expiration,
        )
    except ClientError:
        logger.exception("Failed to generate presigned URL.")
        return None
