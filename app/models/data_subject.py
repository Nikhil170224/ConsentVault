import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class DataSubject(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "data_subjects"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_ref", name="uq_subjects_org_extref"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_anonymized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
