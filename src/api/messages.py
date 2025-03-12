from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.auth import get_current_user
from src.models.models import User
from src.schemas.schemas import (
    ConversationListResponse,
    MessageCreate,
    MessageResponse,
)
from src.services import message_service

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message: MessageCreate,
    current_user: User = Depends(get_current_user),
):
    """Send a direct message to a user"""

    # Check if trying to send message to self
    if message.recipient_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message to yourself",
        )

    try:
        return await message_service.send_message(
            sender_id=current_user.id,
            message_data=message,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Get a list of conversations for the current user"""
    return await message_service.get_conversations(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get("/conversations/{user_id}", response_model=list[MessageResponse])
async def get_conversation_messages(
    user_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
):
    """Get messages between the current user and another user"""

    # Check if trying to get conversation with self
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot have conversation with yourself",
        )

    return await message_service.get_conversation_messages(
        user_id=current_user.id,
        other_user_id=user_id,
        limit=limit,
        before_id=before_id,
    )


@router.post("/conversations/{user_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_conversation_as_read(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """Mark all messages in a conversation as read"""
    await message_service.mark_conversation_as_read(
        user_id=current_user.id,
        other_user_id=user_id,
    )


@router.get("/unread/count", response_model=int)
async def get_unread_message_count(current_user: User = Depends(get_current_user)):
    """Get the total number of unread messages for the current user"""
    return await message_service.get_unread_message_count(user_id=current_user.id)
