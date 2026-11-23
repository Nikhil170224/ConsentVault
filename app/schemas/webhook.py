import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WebhookCreate(BaseModel):
    url: str = Field(min_length=8, max_length=1000)
    secret: str = Field(min_length=8, max_length=255)
    events: list[str] = Field(default_factory=list)


class WebhookUpdate(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None


class WebhookOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
