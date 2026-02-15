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


