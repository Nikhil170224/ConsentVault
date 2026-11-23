import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PurposeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    legal_basis: str = Field(default="CONSENT", pattern=r"^(CONSENT|CONTRACT|LEGAL_OBLIGATION|LEGITIMATE_INTEREST)$")
    is_required: bool = False
    retention_days: int = Field(default=365, gt=0, le=36500)


class PurposeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    legal_basis: str | None = Field(default=None, pattern=r"^(CONSENT|CONTRACT|LEGAL_OBLIGATION|LEGITIMATE_INTEREST)$")
    is_required: bool | None = None
    retention_days: int | None = Field(default=None, gt=0, le=36500)


class PurposeOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    code: str
    name: str
    description: str
    legal_basis: str
    is_required: bool
    retention_days: int
    version: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
