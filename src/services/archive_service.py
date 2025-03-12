"""
Archive service for Glupper.

This module handles URL archiving using AWS SQS and S3 with a separate ArchiveBox backend.
"""

import logging
import re
from typing import Dict, List, Optional, Union
from uuid import UUID

from src.core.db import pool
from src.services.aws_service import (
    check_archive_exists,
    generate_presigned_url,
    get_archive_metadata,
    queue_archive_for_deletion,
    queue_url_for_archiving,
)

# Configure logging
logger = logging.getLogger(__name__)

# URL pattern for extraction
URL_PATTERN = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"


async def extract_urls_from_content(content: str) -> List[str]:
    """Extract URLs from post content"""
    if not content:
        return []

    return re.findall(URL_PATTERN, content)


async def archive_url(url: str, title: Optional[str] = None) -> Optional[str]:
    """
    Queue a URL for archiving.
    
    Args:
        url: The URL to archive
        title: Optional title for the page
        
    Returns:
        The archive_id if successfully queued, None otherwise
    """
    return queue_url_for_archiving(url, title)


async def process_post_urls(
    post_id: UUID, 
    user_id: UUID, 
    content: str, 
    media_urls: List[str], 
    title: Optional[str] = None
) -> Dict[str, str]:
    """
    Process all URLs in a post and queue them for archiving.
    
    Args:
        post_id: The post ID
        user_id: The user ID
        content: The post content
        media_urls: List of media URLs
        title: Optional title for the post
        
    Returns:
        Dictionary mapping URLs to archive_ids
    """
    # Extract URLs from content
    content_urls = await extract_urls_from_content(content)

    # Combine with media URLs
    all_urls = list(set(content_urls + media_urls))

    # For direct URL posts, ensure the URL is included
    if content and content.startswith(('http://', 'https://')) and content not in all_urls:
        all_urls.append(content)

    if not all_urls:
        return {}

    # Queue each URL for archiving
    results = {}
    for url in all_urls:
        archive_id = await archive_url(url, title)
        if archive_id:
            # Store the archive request in the database
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO archived_urls 
                    (post_id, original_url, archive_id, created_at, updated_at)
                    VALUES ($1, $2, $3, NOW(), NOW())
                    ON CONFLICT (post_id, original_url) DO UPDATE
                    SET archive_id = $3, updated_at = NOW()
                    """,
                    post_id,
                    url,
                    archive_id,
                )
            
            results[url] = archive_id

    return results


async def get_archive_status(post_id: UUID) -> Dict[str, Dict]:
    """
    Get the archive status for all URLs in a post.
    
    Args:
        post_id: The post ID
        
    Returns:
        Dictionary with archive status information for each URL
    """
    # Get the archive_ids from the database
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT original_url, archive_id
            FROM archived_urls
            WHERE post_id = $1
            """,
            post_id,
        )

    result = {}
    for row in rows:
        url = row["original_url"]
        archive_id = row["archive_id"]
        
        # Check if the archive exists in S3
        if check_archive_exists(archive_id):
            # Get the archive metadata
            metadata = get_archive_metadata(archive_id)
            if metadata:
                result[url] = {
                    "status": "completed",
                    "archive_id": archive_id,
                    "files": metadata.get("files", []),
                    "main_file": metadata.get("main_file", "index.html"),
                    "timestamp": metadata.get("timestamp", ""),
                }
            else:
                result[url] = {
                    "status": "completed",
                    "archive_id": archive_id,
                    "files": [],
                    "main_file": "index.html",
                }
        else:
            result[url] = {
                "status": "pending",
                "archive_id": archive_id,
            }

    return result


async def get_archived_urls_for_post(post_id: UUID) -> Dict[str, str]:
    """
    Get completed archived URLs for a post.
    
    Args:
        post_id: The post ID
        
    Returns:
        Dictionary mapping original URLs to archived URLs
    """
    status = await get_archive_status(post_id)
    
    result = {}
    for url, info in status.items():
        if info.get("status") == "completed":
            archive_id = info.get("archive_id")
            main_file = info.get("main_file", "index.html")
            
            # Generate a presigned URL for the main file
            archived_url = generate_presigned_url(archive_id, main_file)
            if archived_url:
                result[url] = archived_url

    return result


async def delete_archives_for_post(post_id: UUID) -> bool:
    """
    Queue archives for deletion when a post is deleted.
    
    Args:
        post_id: The post ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get all archive_ids for this post
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT archive_id FROM archived_urls WHERE post_id = $1
                """,
                post_id,
            )
            
            # Delete the archive records
            await conn.execute(
                """
                DELETE FROM archived_urls WHERE post_id = $1
                """,
                post_id,
            )
        
        # Queue each archive for deletion
        for row in rows:
            archive_id = row["archive_id"]
            queue_archive_for_deletion(archive_id)
        
        return True
    except Exception as e:
        logger.error(f"Error deleting archives for post {post_id}: {str(e)}")
        return False