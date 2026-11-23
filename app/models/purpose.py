import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Purpose(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "purposes"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", "version", name="uq_purposes_org_code_ver"),
        CheckConstraint(
            "legal_basis IN ('CONSENT','CONTRACT','LEGAL_OBLIGATION','LEGITIMATE_INTEREST')",
            name="ck_purposes_legal_basis",
        ),
        CheckConstraint("retention_days > 0", name="ck_purposes_retention"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    legal_basis: Mapped[str] = mapped_column(String(32), nullable=False, default="CONSENT")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
