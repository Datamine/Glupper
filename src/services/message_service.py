from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from asyncpg import Connection

from src.core.db import get_connection, release_connection
from src.models.models import Message
from src.schemas.schemas import (
    ConversationListResponse,
    ConversationResponse,
    MessageCreate, 
    MessageResponse
)


async def send_message(
    sender_id: UUID,
    message_data: MessageCreate,
) -> MessageResponse:
    """Send a message from one user to another"""
    conn = await get_connection()
    try:
        # Create the message
        message_id = uuid4()
        now = datetime.utcnow()
        
        # Store the message in the database
        await conn.execute(
            """
            INSERT INTO messages (id, sender_id, recipient_id, content, is_read, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            message_id,
            sender_id,
            message_data.recipient_id,
            message_data.content,
            False,  # Not read initially
            now,
            now,
        )
        
        # Get sender and recipient info for response
        sender = await conn.fetchrow(
            "SELECT username, profile_picture_url FROM users WHERE id = $1",
            sender_id
        )
        
        recipient = await conn.fetchrow(
            "SELECT username, profile_picture_url FROM users WHERE id = $1",
            message_data.recipient_id
        )
        
        if not sender or not recipient:
            raise ValueError("Sender or recipient not found")
        
        return MessageResponse(
            id=message_id,
            sender_id=sender_id,
            sender_username=sender["username"],
            sender_profile_picture_url=sender["profile_picture_url"],
            recipient_id=message_data.recipient_id,
            recipient_username=recipient["username"],
            recipient_profile_picture_url=recipient["profile_picture_url"],
            content=message_data.content,
            is_read=False,
            created_at=now,
        )
    finally:
        await release_connection(conn)


async def get_conversation_messages(
    user_id: UUID,
    other_user_id: UUID,
    limit: int = 50,
    before_id: Optional[UUID] = None,
) -> List[MessageResponse]:
    """Get messages between two users"""
    conn = await get_connection()
    try:
        # Get the messages
        query = """
        WITH message_data AS (
            SELECT 
                m.id, m.sender_id, m.recipient_id, m.content, m.is_read, m.created_at,
                sender.username as sender_username, 
                sender.profile_picture_url as sender_profile_picture_url,
                recipient.username as recipient_username,
                recipient.profile_picture_url as recipient_profile_picture_url
            FROM messages m
            JOIN users sender ON m.sender_id = sender.id
            JOIN users recipient ON m.recipient_id = recipient.id
            WHERE (m.sender_id = $1 AND m.recipient_id = $2)
               OR (m.sender_id = $2 AND m.recipient_id = $1)
        """
        
        params = [user_id, other_user_id, limit]
        
        # Add cursor-based pagination if a before_id is provided
        if before_id:
            query += """
            AND (
                m.created_at < (SELECT created_at FROM messages WHERE id = $4)
                OR (m.created_at = (SELECT created_at FROM messages WHERE id = $4) AND m.id < $4)
            )
            """
            params.append(before_id)
        
        query += """
        ORDER BY m.created_at DESC
        LIMIT $3
        )
        SELECT * FROM message_data
        ORDER BY created_at ASC
        """
        
        rows = await conn.fetch(query, *params)
        
        # Mark messages as read if they were sent to the requesting user
        unread_ids = []
        for row in rows:
            if row["recipient_id"] == user_id and not row["is_read"]:
                unread_ids.append(row["id"])
        
        if unread_ids:
            # Update messages as read in a batch
            await conn.execute(
                """
                UPDATE messages
                SET is_read = TRUE, updated_at = $1
                WHERE id = ANY($2)
                """,
                datetime.utcnow(),
                unread_ids,
            )
        
        # Convert to response objects
        messages = []
        for row in rows:
            messages.append(
                MessageResponse(
                    id=row["id"],
                    sender_id=row["sender_id"],
                    sender_username=row["sender_username"],
                    sender_profile_picture_url=row["sender_profile_picture_url"],
                    recipient_id=row["recipient_id"],
                    recipient_username=row["recipient_username"],
                    recipient_profile_picture_url=row["recipient_profile_picture_url"],
                    content=row["content"],
                    is_read=True if row["recipient_id"] == user_id else row["is_read"],
                    created_at=row["created_at"],
                )
            )
            
        return messages
    finally:
        await release_connection(conn)


async def get_conversations(
    user_id: UUID, 
    limit: int = 20, 
    offset: int = 0
) -> ConversationListResponse:
    """
    Get a list of conversations for a user
    
    This returns a list of users that the current user has exchanged messages with,
    along with the latest message and unread count for each conversation.
    """
    conn = await get_connection()
    try:
        # This query finds all users with whom the current user has exchanged messages
        # It includes the last message and unread count for each conversation
        query = """
        WITH conversations AS (
            SELECT DISTINCT
                CASE
                    WHEN m.sender_id = $1 THEN m.recipient_id
                    ELSE m.sender_id
                END AS other_user_id
            FROM messages m
            WHERE m.sender_id = $1 OR m.recipient_id = $1
        ),
        last_messages AS (
            SELECT DISTINCT ON (
                LEAST(m.sender_id, m.recipient_id),
                GREATEST(m.sender_id, m.recipient_id)
            )
                m.id, m.sender_id, m.recipient_id, m.content, m.is_read, m.created_at,
                CASE
                    WHEN m.sender_id = $1 THEN m.recipient_id
                    ELSE m.sender_id
                END AS other_user_id
            FROM messages m
            WHERE m.sender_id = $1 OR m.recipient_id = $1
            ORDER BY 
                LEAST(m.sender_id, m.recipient_id),
                GREATEST(m.sender_id, m.recipient_id),
                m.created_at DESC
        ),
        unread_counts AS (
            SELECT
                sender_id AS other_user_id,
                COUNT(*) AS unread_count
            FROM messages
            WHERE recipient_id = $1 AND is_read = FALSE
            GROUP BY sender_id
        )
        SELECT
            u.id AS user_id,
            u.username,
            u.profile_picture_url,
            lm.id AS message_id,
            lm.sender_id,
            lm.recipient_id,
            lm.content,
            lm.is_read,
            lm.created_at AS message_created_at,
            COALESCE(uc.unread_count, 0) AS unread_count,
            (
                SELECT MIN(created_at)
                FROM messages
                WHERE 
                    (sender_id = $1 AND recipient_id = u.id) OR
                    (sender_id = u.id AND recipient_id = $1)
            ) AS conversation_created_at
        FROM conversations c
        JOIN users u ON c.other_user_id = u.id
        JOIN last_messages lm ON c.other_user_id = lm.other_user_id
        LEFT JOIN unread_counts uc ON c.other_user_id = uc.other_user_id
        ORDER BY lm.created_at DESC
        LIMIT $2 OFFSET $3
        """
        
        rows = await conn.fetch(query, user_id, limit, offset)
        
        # Get sender and recipient info for each conversation
        conversations = []
        for row in rows:
            sender_id = row["sender_id"]
            recipient_id = row["recipient_id"]
            
            # Get sender info
            sender = await conn.fetchrow(
                "SELECT username, profile_picture_url FROM users WHERE id = $1",
                sender_id
            )
            
            # Get recipient info
            recipient = await conn.fetchrow(
                "SELECT username, profile_picture_url FROM users WHERE id = $1",
                recipient_id
            )
            
            if not sender or not recipient:
                continue
                
            last_message = MessageResponse(
                id=row["message_id"],
                sender_id=sender_id,
                sender_username=sender["username"],
                sender_profile_picture_url=sender["profile_picture_url"],
                recipient_id=recipient_id,
                recipient_username=recipient["username"],
                recipient_profile_picture_url=recipient["profile_picture_url"],
                content=row["content"],
                is_read=row["is_read"],
                created_at=row["message_created_at"],
            )
            
            conversations.append(
                ConversationResponse(
                    user_id=row["user_id"],
                    username=row["username"],
                    profile_picture_url=row["profile_picture_url"],
                    last_message=last_message,
                    unread_count=row["unread_count"],
                    created_at=row["conversation_created_at"],
                )
            )
        
        return ConversationListResponse(conversations=conversations)
    finally:
        await release_connection(conn)


async def mark_conversation_as_read(user_id: UUID, other_user_id: UUID) -> int:
    """Mark all messages in a conversation as read for the current user"""
    conn = await get_connection()
    try:
        result = await conn.execute(
            """
            UPDATE messages
            SET is_read = TRUE, updated_at = $1
            WHERE recipient_id = $2 AND sender_id = $3 AND is_read = FALSE
            """,
            datetime.utcnow(),
            user_id,
            other_user_id,
        )
        
        # Return the number of messages marked as read
        return int(result.split(" ")[1]) if result else 0
    finally:
        await release_connection(conn)


async def get_unread_message_count(user_id: UUID) -> int:
    """Get the total number of unread messages for a user"""
    conn = await get_connection()
    try:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE recipient_id = $1 AND is_read = FALSE",
            user_id
        )
        return result or 0
    finally:
        await release_connection(conn)