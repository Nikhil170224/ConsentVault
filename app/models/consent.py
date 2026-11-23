import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Consent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint("status IN ('GRANTED','WITHDRAWN','EXPIRED')", name="ck_consents_status"),
        CheckConstraint("source IN ('web','mobile','api')", name="ck_consents_source"),
        Index(
            "uq_consents_active_subject_purpose", "data_subject_id", "purpose_id",
            unique=True, postgresql_where=text("status = 'GRANTED'"),
            sqlite_where=text("status = 'GRANTED'"),
        ),
        Index("ix_consents_subject_status", "data_subject_id", "status"),
        Index("ix_consents_expires", "expires_at"),
    )

    data_subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purposes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="GRANTED")
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="api")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
