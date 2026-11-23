
from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.models.consent_event import ConsentEvent
from app.models.data_subject import DataSubject
from app.models.dsr import DsrRequest
from app.models.purpose import Purpose


class ExportService:
    """Builds the ACCESS/EXPORT JSON bundle for a data subject."""

    def __init__(self, db: Session):
        self.db = db

    def build_bundle(self, subject: DataSubject) -> dict:
        consents = self.db.query(Consent).filter(Consent.data_subject_id == subject.id).all()
        events = (
            self.db.query(ConsentEvent)
            .filter(ConsentEvent.data_subject_id == subject.id)
            .order_by(ConsentEvent.created_at.asc())
            .all()
        )
        dsrs = self.db.query(DsrRequest).filter(DsrRequest.data_subject_id == subject.id).all()
        purposes = {str(p.id): p for p in self.db.query(Purpose).all()}
        return {
            "data_subject": {
                "id": str(subject.id), "external_ref": subject.external_ref,
                "email": subject.email, "organization_id": str(subject.organization_id),
                "is_anonymized": subject.is_anonymized,
                "created_at": subject.created_at.isoformat() if subject.created_at else None,
            },
            "consents": [
                {
                    "id": str(c.id), "purpose_id": str(c.purpose_id),
                    "purpose_code": (purposes[str(c.purpose_id)].code if str(c.purpose_id) in purposes else None),
                    "status": c.status,
                    "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                    "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "source": c.source, "policy_version": c.policy_version,
                }
                for c in consents
            ],
            "consent_history": [
                {
                    "id": str(e.id), "event_type": e.event_type,
                    "old_status": e.old_status, "new_status": e.new_status,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "event_hash": e.event_hash,
                }
                for e in events
            ],
            "dsr_requests": [
                {"id": str(d.id), "type": d.type, "status": d.status,
                 "created_at": d.created_at.isoformat() if d.created_at else None}
                for d in dsrs
            ],
        }
