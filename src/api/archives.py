from typing import Annotated, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.auth import get_current_user
from src.models.models import User
from src.services.archive_service import (
    get_archive_status,
    get_archived_urls_for_post,
)

router = APIRouter(prefix="/api/v1/archives", tags=["archives"])


@router.get("/{post_id}", status_code=status.HTTP_200_OK)
async def get_post_archives(
    post_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    include_pending: bool = Query(False, description="Include pending archives in the response"),
) -> dict[str, Dict]:
    """
    Get archive information for a post.

    Parameters:
    - **post_id**: UUID of the post
    - **include_pending**: Whether to include pending archives in the response
    - **current_user**: User object from token authentication dependency

    Returns:
    - Dictionary with archive information

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If no archives found
    """
    # Get archive status for all URLs
    if include_pending:
        archive_info = await get_archive_status(post_id)
    else:
        # Only get completed archives
        archives = await get_archived_urls_for_post(post_id)
        if archives:
            archive_info = {"completed": archives}
        else:
            archive_info = {}

    if not archive_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No archives found for this post",
        )

    return {"archives": archive_info}


@router.get("/{post_id}/url", status_code=status.HTTP_200_OK)
async def get_archive_for_url(
    post_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    url: str = Query(..., description="The URL to get the archive for"),
) -> dict[str, Optional[str]]:
    """
    Get the archive for a specific URL in a post.

    Parameters:
    - **post_id**: UUID of the post
    - **url**: The URL to get the archive for
    - **current_user**: User object from token authentication dependency

    Returns:
    - Dictionary with archive URL

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If archive not found
    - **425 Too Early**: If archive is still being processed
    """
    # Get archive status for all URLs
    status_info = await get_archive_status(post_id)

    if url not in status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No archive found for this URL",
        )

    archive_info = status_info[url]

    # Check status
    if archive_info["status"] == "pending" or archive_info["status"] == "processing":
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"Archive is still {archive_info['status']}",
        )
    elif archive_info["status"] == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Archive failed to process",
        )

    # Return the archive URL
    archive_url = archive_info.get("archived_url") or archive_info.get("s3_location")
    if not archive_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archive URL not found",
        )

    return {"archived_url": archive_url}
