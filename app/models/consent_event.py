import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, UUIDMixin


class ConsentEvent(UUIDMixin, Base):
    """Append-only audit record. UPDATE/DELETE blocked by DB trigger (migration)."""

    __tablename__ = "consent_events"
    __table_args__ = (
        Index("ix_consent_events_org_created", "organization_id", "created_at"),
        Index("ix_consent_events_subject", "data_subject_id", "created_at"),
        Index("ix_consent_events_meta_gin", "metadata", postgresql_using="gin"),
    )

    consent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_subjects.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
