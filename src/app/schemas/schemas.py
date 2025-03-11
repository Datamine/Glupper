from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# Auth Schemas
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    bio: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    follower_count: int
    following_count: int
    created_at: datetime

class UserUpdateRequest(BaseModel):
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None

# Post Schemas
class PostCreate(BaseModel):
    content: str
    media_urls: Optional[List[str]] = None

class CommentCreate(BaseModel):
    content: str
    media_urls: Optional[List[str]] = None

class PostResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    profile_picture_url: Optional[str] = None
    content: str
    media_urls: Optional[List[str]] = None
    like_count: int
    comment_count: int
    repost_count: int
    is_repost: bool = False
    original_post_id: Optional[UUID] = None
    liked_by_user: Optional[bool] = None
    archived_urls: Optional[Dict[str, str]] = None
    created_at: datetime

class PostDetailResponse(PostResponse):
    comments: List[PostResponse] = []

class FeedResponse(BaseModel):
    posts: List[PostResponse]
    next_cursor: Optional[str] = None

class TrendingTopic(BaseModel):
    name: str
    post_count: int