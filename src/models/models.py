from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


# Database models
class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    username: str
    email: EmailStr
    password_hash: str
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Post(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    content: str
    media_urls: list[str] = Field(default_factory=list)
    like_count: int = 0
    comment_count: int = 0
    repost_count: int = 0
    is_repost: bool = False
    original_post_id: Optional[UUID] = None
    archived_urls: dict[str, str] = Field(default_factory=dict)  # original_url -> archived_url
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Like(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    post_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Follow(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    follower_id: UUID  # User who follows
    followee_id: UUID  # User being followed
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Timeline(BaseModel):
    """Cache model for user timeline"""

    user_id: UUID
    post_ids: list[UUID] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
