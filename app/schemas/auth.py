import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)
    organization_slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="org_admin", pattern=r"^(org_admin|dpo|data_subject)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organization_slug: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
