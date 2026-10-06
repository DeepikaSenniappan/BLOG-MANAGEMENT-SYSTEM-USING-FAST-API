from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=50000)


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=50000)


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    author_id: int
    created_at: datetime
    image_url: str | None = None


class PaginatedPosts(BaseModel):
    items: list[PostOut]
    total: int
    page: int
    limit: int
    total_pages: int


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: int
    user_id: int
    text: str
    created_at: datetime


class LikeOut(BaseModel):
    liked: bool
    likes_count: int
