import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.repositories.consent_repo import ConsentRepository, get_latest_purpose, get_or_create_subject
from app.services.audit_service import AuditService
from app.services.webhook_service import WebhookService


class ConsentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ConsentRepository(db)
        self.audit = AuditService(db)

    def grant(
        self, organization_id: uuid.UUID, external_ref: str, email: str | None,
        purposes: list, source: str, actor_id: str | None,
        ip_address: str | None = None, user_agent: str | None = None,
        dispatch_webhooks: bool = True,
    ) -> list[Consent]:
        subject = get_or_create_subject(self.db, organization_id, external_ref, email)
        results: list[Consent] = []
        now = datetime.now(UTC)
        for item in purposes:
            purpose = get_latest_purpose(self.db, organization_id, item.purpose_code)
            if purpose is None:
                raise HTTPException(status_code=404, detail=f"Purpose '{item.purpose_code}' not found")
            existing = self.repo.get_active(subject.id, purpose.id)
            if existing is not None:
                # Idempotent: already granted -> return as-is, no new event.
                results.append(existing)
                continue
            consent = Consent(
                data_subject_id=subject.id, purpose_id=purpose.id, status="GRANTED",
                granted_at=now, expires_at=item.expires_at, source=source,
                ip_address=ip_address, user_agent=user_agent, policy_version=item.policy_version,
            )
            self.db.add(consent)
            self.db.flush()
            self.audit.record_event(
                consent.id, subject.id, organization_id, "consent.granted", None, "GRANTED",
                actor_type="user", actor_id=actor_id,
                metadata={"purpose_code": purpose.code, "source": source},
            )
            results.append(consent)
        self.db.commit()
        for c in results:
            self.db.refresh(c)
        if dispatch_webhooks:
            for c in results:
                WebhookService(self.db).dispatch(
                    organization_id, "consent.granted",
                    {"consent_id": str(c.id), "data_subject_id": str(subject.id)},
                )
        return results

    def withdraw(self, consent_id: uuid.UUID, organization_id: uuid.UUID, actor_id: str | None) -> Consent:
        consent = self.db.get(Consent, consent_id)
        if consent is None:
            raise HTTPException(status_code=404, detail="Consent not found")
        # Tenant check via purpose's org.
        from app.models.purpose import Purpose

        purpose = self.db.get(Purpose, consent.purpose_id)
        if purpose is None or purpose.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Consent not found")
        if consent.status != "GRANTED":
            raise HTTPException(status_code=409, detail=f"Consent is {consent.status}, cannot withdraw")
        if purpose.is_required:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This purpose is required for the service to function and cannot be "
                    "withdrawn directly. Use the documented alternative flow: contact the "
                    "DPO or delete your account (DSR DELETE) to stop this processing."
                ),
            )
        old = consent.status
        consent.status = "WITHDRAWN"
        consent.withdrawn_at = datetime.now(UTC)
        self.db.flush()
        self.audit.record_event(
            consent.id, consent.data_subject_id, organization_id, "consent.withdrawn", old, "WITHDRAWN",
            actor_type="user", actor_id=actor_id, metadata={"purpose_code": purpose.code},
        )
        self.db.commit()
        self.db.refresh(consent)
        WebhookService(self.db).dispatch(
            organization_id, "consent.withdrawn",
            {"consent_id": str(consent.id), "data_subject_id": str(consent.data_subject_id)},
        )
        return consent

    def check(self, organization_id: uuid.UUID, data_subject_id: uuid.UUID, purpose_code: str) -> Consent | None:
        return self.repo.check_consent(organization_id, data_subject_id, purpose_code)

    def sweep_expired(self) -> int:
        """Scheduled sweep: mark expired GRANTED consents as EXPIRED with audit events."""
        now = datetime.now(UTC)
        expired = self.repo.expired_granted(now)
        from app.models.purpose import Purpose

        for consent in expired:
            purpose = self.db.get(Purpose, consent.purpose_id)
            org_id = purpose.organization_id if purpose else uuid.uuid4()
            old = consent.status
            consent.status = "EXPIRED"
            self.db.flush()
            self.audit.record_event(
                consent.id, consent.data_subject_id, org_id, "consent.expired", old, "EXPIRED",
                actor_type="system", actor_id=None, metadata={"sweep": True},
            )
        self.db.commit()
        return len(expired)
