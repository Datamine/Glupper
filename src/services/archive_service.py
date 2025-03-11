from datetime import datetime
import asyncio
import httpx
import logging
import re
from typing import Optional
from uuid import UUID

from glupper.app.core.db import pool

# Configure logging
logger = logging.getLogger(__name__)

# URL pattern for extraction
URL_PATTERN = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"


async def extract_urls_from_content(content: str) -> list[str]:
    """Extract URLs from post content"""
    if not content:
        return []
    
    return re.findall(URL_PATTERN, content)


async def archive_url(url: str) -> Optional[str]:
    """
    Archive a URL using the Archive Box API
    Returns the archived URL if successful, None otherwise
    """
    try:
        # Configure this with your ArchiveBox setup
        archive_endpoint = "http://localhost:8000/api/archive/"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Content-Type": "application/json"}
            payload = {"url": url}
            
            response = await client.post(archive_endpoint, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                # The exact response structure depends on your ArchiveBox API
                # This is an example - adjust according to actual API response
                archive_url = result.get("archive_url")
                if archive_url is not None:
                    return str(archive_url)
                return None
            
            logger.error(f"Failed to archive URL {url}: {response.status_code} {response.text}")
            return None
                
    except Exception as e:
        logger.error(f"Error archiving URL {url}: {str(e)}")
        return None


async def process_post_urls(post_id: UUID, user_id: UUID, content: str, media_urls: list[str]) -> None:
    """Process all URLs in a post and archive them"""
    # Extract URLs from content
    content_urls = await extract_urls_from_content(content)
    
    # Combine with media URLs
    all_urls = list(set(content_urls + media_urls))
    
    if not all_urls:
        return
    
    # Archive each URL and store the results
    archive_tasks = [archive_url(url) for url in all_urls]
    
    # Wait for all archiving tasks to complete
    archived_urls = await asyncio.gather(*archive_tasks)
    
    # Create mapping of original URL to archived URL
    url_mapping = {
        original: archived
        for original, archived in zip(all_urls, archived_urls, strict=False)
        if archived is not None  # Only include successful archives
    }
    
    if not url_mapping:
        return
    
    # Store the archived URLs in the database
    async with pool.acquire() as conn:
        for original_url, archived_url in url_mapping.items():
            await conn.execute("""
                INSERT INTO archived_urls (post_id, original_url, archived_url, created_at)
                VALUES ($1, $2, $3, $4)
            """, post_id, original_url, archived_url, datetime.now())
    
    logger.info(f"Archived {len(url_mapping)} URLs for post {post_id}")


async def get_archived_urls_for_post(post_id: UUID) -> dict[str, str]:
    """Get all archived URLs for a post"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT original_url, archived_url
            FROM archived_urls
            WHERE post_id = $1
        """, post_id)
    
    return {row["original_url"]: row["archived_url"] for row in rows}