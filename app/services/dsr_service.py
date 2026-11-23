import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_pii
from app.models.data_subject import DataSubject
from app.models.dsr import DsrRequest, DsrStatusHistory
from app.services.export_service import ExportService
from app.services.webhook_service import WebhookService

# Strict state machine: from -> allowed tos. Terminal: COMPLETED, REJECTED.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "RECEIVED": {"VERIFYING", "REJECTED"},
    "VERIFYING": {"IN_PROGRESS", "REJECTED"},
    "IN_PROGRESS": {"COMPLETED", "REJECTED"},
    "COMPLETED": set(),
    "REJECTED": set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


class DsrService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, organization_id: uuid.UUID, data_subject_id: uuid.UUID, dsr_type: str, details: str | None, actor_id: str | None) -> DsrRequest:
        sla_days = get_settings().dsr_sla_days
        now = datetime.now(UTC)
        dsr = DsrRequest(
            organization_id=organization_id, data_subject_id=data_subject_id,
            type=dsr_type, status="RECEIVED", due_date=now + timedelta(days=sla_days),
            details=details,
        )
        self.db.add(dsr)
        self.db.flush()
        self.db.add(DsrStatusHistory(dsr_id=dsr.id, from_status=None, to_status="RECEIVED", changed_by=actor_id))
        self.db.commit()
        self.db.refresh(dsr)
        WebhookService(self.db).dispatch(organization_id, "dsr.created", {"dsr_id": str(dsr.id), "type": dsr.type})
        return dsr

    def transition(self, dsr: DsrRequest, target: str, actor_id: str | None, note: str | None = None, rejection_reason: str | None = None) -> DsrRequest:
        if not can_transition(dsr.status, target):
            raise HTTPException(
                status_code=422,
                detail=f"Illegal DSR transition {dsr.status} -> {target}. Allowed: {sorted(ALLOWED_TRANSITIONS.get(dsr.status, set()))}",
            )
        old = dsr.status
        dsr.status = target
        if target == "REJECTED":
            dsr.rejection_reason = rejection_reason or note
        if target == "COMPLETED":
            dsr.completed_at = datetime.now(UTC)
            self._fulfill(dsr)
        self.db.add(DsrStatusHistory(dsr_id=dsr.id, from_status=old, to_status=target, changed_by=actor_id, note=note))
        self.db.commit()
        self.db.refresh(dsr)
        if target == "COMPLETED":
            WebhookService(self.db).dispatch(dsr.organization_id, "dsr.completed", {"dsr_id": str(dsr.id), "type": dsr.type})
        return dsr

    def _fulfill(self, dsr: DsrRequest) -> None:
        subject = self.db.get(DataSubject, dsr.data_subject_id)
        if subject is None:
            return
        if dsr.type in ("ACCESS", "EXPORT"):
            bundle = ExportService(self.db).build_bundle(subject)
            dsr.result_data = bundle
            dsr.result_ref = f"export:{dsr.id}"
        elif dsr.type == "DELETE":
            self.anonymize_subject(subject)
            dsr.result_ref = "anonymized"
        elif dsr.type == "CORRECTION":
            dsr.result_ref = "corrected"

    def anonymize_subject(self, subject: DataSubject) -> None:
        """Irreversibly anonymize PII while preserving the audit hash chain.

        Consent events reference the subject by UUID only and contain no email,
        so replacing email/external_ref does not break hash verification.
        Legally required consent records are retained in anonymized form.
        """
        if subject.email:
            subject.email = hash_pii(subject.email) + "@anonymized.local"
        subject.external_ref = hash_pii(subject.external_ref)
        subject.is_anonymized = True
        self.db.flush()

    def overdue(self, organization_id: uuid.UUID) -> list[DsrRequest]:
        now = datetime.now(UTC)
        return list(
            self.db.query(DsrRequest)
            .filter(
                DsrRequest.organization_id == organization_id,
                DsrRequest.status.in_(["RECEIVED", "VERIFYING", "IN_PROGRESS"]),
                DsrRequest.due_date < now,
            )
            .all()
        )
