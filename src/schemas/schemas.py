from datetime import datetime
from typing import Any, Optional, Union
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


