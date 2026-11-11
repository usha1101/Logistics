from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    full_name: str = Field(default="", max_length=128)
    role: UserRole = UserRole.ANALYST
    is_active: bool = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    full_name: str = Field(default="", max_length=128)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.ANALYST


class UserRoleUpdate(BaseModel):
    role: UserRole = Field(..., description="Target role to assign to the user")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    username_or_email: Optional[str] = None
    password: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_identifier(self) -> "LoginRequest":
        identifier = self.username_or_email or self.username or self.email
        if not identifier:
            raise ValueError("Either username, email, or username_or_email must be provided")
        return self

    @property
    def identifier(self) -> str:
        return (self.username_or_email or self.username or str(self.email or "")).strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifespan in seconds")
    user: UserRead

