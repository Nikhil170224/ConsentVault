import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DsrCreate(BaseModel):
    external_ref: str | None = None
    data_subject_id: uuid.UUID | None = None
    type: str = Field(pattern=r"^(ACCESS|EXPORT|DELETE|CORRECTION)$")
    details: str | None = None


class DsrStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(RECEIVED|VERIFYING|IN_PROGRESS|COMPLETED|REJECTED)$")
    note: str | None = None
    rejection_reason: str | None = None


class DsrOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    data_subject_id: uuid.UUID
    type: str
    status: str
    due_date: datetime | None = None
    completed_at: datetime | None = None
    rejection_reason: str | None = None
    result_ref: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
