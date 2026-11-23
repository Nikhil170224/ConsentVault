import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.models.data_subject import DataSubject
from app.models.purpose import Purpose
from app.repositories.base import BaseRepository


class ConsentRepository(BaseRepository[Consent]):
    def __init__(self, db: Session):
        super().__init__(db, Consent)

    def get_active(self, data_subject_id: uuid.UUID, purpose_id: uuid.UUID) -> Consent | None:
        return (
            self.db.query(Consent)
            .filter(
                Consent.data_subject_id == data_subject_id,
                Consent.purpose_id == purpose_id,
                Consent.status == "GRANTED",
            )
            .first()
        )

    def get_latest(self, data_subject_id: uuid.UUID, purpose_id: uuid.UUID) -> Consent | None:
        return (
            self.db.query(Consent)
            .filter(Consent.data_subject_id == data_subject_id, Consent.purpose_id == purpose_id)
            .order_by(Consent.created_at.desc())
            .first()
        )

    def check_consent(self, organization_id: uuid.UUID, data_subject_id: uuid.UUID, purpose_code: str) -> Consent | None:
        """Optimized check: single indexed join, latest active purpose version."""
        now = datetime.now(UTC)
        return (
            self.db.query(Consent)
            .join(Purpose, Purpose.id == Consent.purpose_id)
            .filter(
                Purpose.organization_id == organization_id,
                Purpose.code == purpose_code,
                Consent.data_subject_id == data_subject_id,
                Consent.status == "GRANTED",
            )
            .filter((Consent.expires_at.is_(None)) | (Consent.expires_at > now))
            .first()
        )

    def expired_granted(self, now: datetime) -> list[Consent]:
        return list(
            self.db.query(Consent)
            .filter(Consent.status == "GRANTED", Consent.expires_at.isnot(None), Consent.expires_at <= now)
            .all()
        )


def get_or_create_subject(db: Session, organization_id: uuid.UUID, external_ref: str, email: str | None) -> DataSubject:
    subject = (
        db.query(DataSubject)
        .filter(DataSubject.organization_id == organization_id, DataSubject.external_ref == external_ref)
        .first()
    )
    if subject is None:
        subject = DataSubject(organization_id=organization_id, external_ref=external_ref, email=email)
        db.add(subject)
        db.flush()
    elif email and not subject.email:
        subject.email = email
    return subject


def get_latest_purpose(db: Session, organization_id: uuid.UUID, code: str) -> Purpose | None:
    return (
        db.query(Purpose)
        .filter(Purpose.organization_id == organization_id, Purpose.code == code, Purpose.is_active.is_(True))
        .order_by(Purpose.version.desc())
        .first()
    )
