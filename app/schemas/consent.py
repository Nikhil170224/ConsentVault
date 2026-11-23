import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ConsentGrantItem(BaseModel):
    purpose_code: str
    policy_version: str | None = None
    expires_at: datetime | None = None


class ConsentGrantRequest(BaseModel):
    external_ref: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    purposes: list[ConsentGrantItem] = Field(min_length=1)
    source: str = Field(default="api", pattern=r"^(web|mobile|api)$")


class ConsentOut(BaseModel):
    id: uuid.UUID
    data_subject_id: uuid.UUID
    purpose_id: uuid.UUID
    status: str
    granted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    expires_at: datetime | None = None
    source: str
    policy_version: str | None = None

    model_config = {"from_attributes": True}


class ConsentCheckRequest(BaseModel):
    external_ref: str | None = None
    data_subject_id: uuid.UUID | None = None
    purpose_code: str


class ConsentCheckResponse(BaseModel):
    has_consent: bool
    status: str | None = None
    purpose_code: str
    expires_at: datetime | None = None


class ConsentEventOut(BaseModel):
    id: uuid.UUID
    consent_id: uuid.UUID
    event_type: str
    old_status: str | None = None
    new_status: str | None = None
    actor_type: str
    created_at: datetime
    event_hash: str

    model_config = {"from_attributes": True}
