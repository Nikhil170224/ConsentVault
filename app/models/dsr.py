import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin


class DsrRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dsr_requests"
    __table_args__ = (
        CheckConstraint("type IN ('ACCESS','EXPORT','DELETE','CORRECTION')", name="ck_dsr_type"),
        CheckConstraint(
            "status IN ('RECEIVED','VERIFYING','IN_PROGRESS','COMPLETED','REJECTED')",
            name="ck_dsr_status",
        ),
        Index(
            "ix_dsr_pending", "organization_id", "due_date",
            postgresql_where=text("status IN ('RECEIVED','VERIFYING','IN_PROGRESS')"),
            sqlite_where=text("status IN ('RECEIVED','VERIFYING','IN_PROGRESS')"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RECEIVED")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_data: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class DsrStatusHistory(UUIDMixin, Base):
    __tablename__ = "dsr_status_history"

    dsr_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dsr_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=__import__("sqlalchemy").func.now(), nullable=False)
