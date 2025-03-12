from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


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
    title: str
    url: str
    
    @validator('title')
    def validate_title(cls, v):
        if not v or len(v) > 100:
            raise ValueError('Title must be between 1 and 100 characters')
        return v
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class CommentCreate(BaseModel):
    content: str
    media_urls: Optional[list[str]] = None
    
    @validator('content')
    def validate_content_length(cls, v):
        if len(v) > 300:
            raise ValueError('Comment content must be 300 characters or less')
        return v


class PostResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    profile_picture_url: Optional[str] = None
    title: Optional[str] = None  # For top-level posts
    url: Optional[str] = None    # For top-level posts
    content: Optional[str] = None  # For comments only
    media_urls: Optional[list[str]] = None
    like_count: int
    comment_count: int
    repost_count: int
    is_repost: bool = False
    original_post_id: Optional[UUID] = None
    parent_post_id: Optional[UUID] = None  # For comments, the post they're replying to
    is_comment: bool = False
    liked_by_user: Optional[bool] = None
    archived_urls: Optional[dict[str, str]] = None
    created_at: datetime


class PostDetailResponse(PostResponse):
    comments: list[PostResponse] = []


class FeedResponse(BaseModel):
    posts: list[PostResponse]
    next_cursor: Optional[str] = None


class TrendingTopic(BaseModel):
    name: str
    post_count: int


# Redis Data Models
class RedisModel(BaseModel):
    """Base model for Redis data structures with serialization/deserialization methods"""
    
    class Config:
        """Configuration for Pydantic models"""
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat(),
        }
        
    @classmethod
    def from_redis(cls, data: Union[str, bytes, dict, None]) -> Optional["RedisModel"]:
        """Create an instance from Redis data"""
        if data is None:
            return None
            
        if isinstance(data, (str, bytes)):
            import json
            try:
                data_dict = json.loads(data)
                return cls.parse_obj(data_dict)
            except Exception as e:
                import logging
                logging.error(f"Error parsing Redis data: {e}")
                return None
        
        return cls.parse_obj(data)
        
    def to_redis(self) -> str:
        """Convert to JSON string for Redis storage"""
        import json
        return json.dumps(self.dict())


class RedisPost(RedisModel):
    """Post model for Redis storage"""
    id: Union[UUID, str]
    user_id: Union[UUID, str]
    username: str
    profile_picture_url: Optional[str] = None
    title: Optional[str] = None  # For top-level posts
    url: Optional[str] = None    # For top-level posts
    content: Optional[str] = None  # For comments only
    media_urls: List[str] = Field(default_factory=list)
    like_count: int = 0
    comment_count: int = 0
    repost_count: int = 0
    is_repost: bool = False
    original_post_id: Optional[Union[UUID, str]] = None
    parent_post_id: Optional[Union[UUID, str]] = None  # For comments
    is_comment: bool = False
    created_at: Union[datetime, str]
    archived_urls: Optional[Dict[str, str]] = None
    
    @validator('id', 'user_id', 'original_post_id', 'parent_post_id', pre=True)
    def validate_uuid(cls, v):
        """Validate and convert UUID strings to UUID objects"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                return v
        return v
        
    @validator('created_at', pre=True)
    def validate_datetime(cls, v):
        """Validate and convert datetime strings to datetime objects"""
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return v
        return v
    
    def to_post_response(self) -> PostResponse:
        """Convert to PostResponse for API output"""
        return PostResponse(
            id=self.id,
            user_id=self.user_id,
            username=self.username,
            profile_picture_url=self.profile_picture_url,
            title=self.title,
            url=self.url,
            content=self.content,
            media_urls=self.media_urls,
            like_count=self.like_count,
            comment_count=self.comment_count,
            repost_count=self.repost_count,
            is_repost=self.is_repost,
            original_post_id=self.original_post_id,
            parent_post_id=self.parent_post_id,
            is_comment=self.is_comment,
            archived_urls=self.archived_urls,
            created_at=self.created_at,
        )
    
    @classmethod
    def from_post_response(cls, post: PostResponse) -> "RedisPost":
        """Create RedisPost from PostResponse"""
        return cls(
            id=post.id,
            user_id=post.user_id,
            username=post.username,
            profile_picture_url=post.profile_picture_url,
            title=post.title,
            url=post.url,
            content=post.content,
            media_urls=post.media_urls or [],
            like_count=post.like_count,
            comment_count=post.comment_count,
            repost_count=post.repost_count,
            is_repost=post.is_repost,
            original_post_id=post.original_post_id,
            parent_post_id=post.parent_post_id,
            is_comment=post.is_comment,
            archived_urls=post.archived_urls,
            created_at=post.created_at,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedisPost":
        """Create RedisPost from dictionary"""
        return cls(**data)


class RedisTimeline(RedisModel):
    """Timeline model for Redis storage"""
    user_id: Union[UUID, str]
    posts: List[RedisPost] = Field(default_factory=list)
    last_updated: Union[datetime, str] = Field(default_factory=datetime.now)
    
    @validator('user_id', pre=True)
    def validate_uuid(cls, v):
        """Validate and convert UUID strings to UUID objects"""
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                return v
        return v
        
    @validator('last_updated', pre=True)
    def validate_datetime(cls, v):
        """Validate and convert datetime strings to datetime objects"""
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return v
        return v
    
    @validator('posts', pre=True)
    def validate_posts(cls, v):
        """Validate and convert post dictionaries to RedisPost objects"""
        if isinstance(v, list):
            return [
                RedisPost.from_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        return v


class RedisTrending(RedisModel):
    """Trending posts model for Redis storage"""
    posts: List[RedisPost] = Field(default_factory=list)
    last_updated: Union[datetime, str] = Field(default_factory=datetime.now)
    
    @validator('last_updated', pre=True)
    def validate_datetime(cls, v):
        """Validate and convert datetime strings to datetime objects"""
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                return v
        return v
    
    @validator('posts', pre=True)
    def validate_posts(cls, v):
        """Validate and convert post dictionaries to RedisPost objects"""
        if isinstance(v, list):
            return [
                RedisPost.from_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        return v
