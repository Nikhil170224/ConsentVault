import hashlib
import json
import uuid

from sqlalchemy.orm import Session

from app.models.consent_event import ConsentEvent

GENESIS_HASH = "0" * 64


def canonical_payload(event: dict) -> str:
    """Deterministic canonical JSON for hashing (sorted keys, compact separators)."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)


def compute_event_hash(prev_hash: str, payload: dict) -> str:
    material = prev_hash + canonical_payload(payload)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_event_payload(
    consent_id: uuid.UUID, data_subject_id: uuid.UUID, organization_id: uuid.UUID,
    event_type: str, old_status: str | None, new_status: str | None,
    actor_type: str, actor_id: str | None, metadata: dict,
) -> dict:
    return {
        "consent_id": str(consent_id),
        "data_subject_id": str(data_subject_id),
        "organization_id": str(organization_id),
        "event_type": event_type,
        "old_status": old_status,
        "new_status": new_status,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "metadata": metadata or {},
    }


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def last_hash(self, organization_id: uuid.UUID) -> str:
        last = (
            self.db.query(ConsentEvent)
            .filter(ConsentEvent.organization_id == organization_id)
            .order_by(ConsentEvent.created_at.desc(), ConsentEvent.id.desc())
            .first()
        )
        return last.event_hash if last else GENESIS_HASH

    def record_event(
        self, consent_id: uuid.UUID, data_subject_id: uuid.UUID, organization_id: uuid.UUID,
        event_type: str, old_status: str | None, new_status: str | None,
        actor_type: str = "user", actor_id: str | None = None, metadata: dict | None = None,
    ) -> ConsentEvent:
        metadata = metadata or {}
        prev_hash = self.last_hash(organization_id)
        payload = build_event_payload(
            consent_id, data_subject_id, organization_id, event_type,
            old_status, new_status, actor_type, actor_id, metadata,
        )
        event_hash = compute_event_hash(prev_hash, payload)
        event = ConsentEvent(
            consent_id=consent_id, data_subject_id=data_subject_id,
            organization_id=organization_id, event_type=event_type,
            old_status=old_status, new_status=new_status, actor_type=actor_type,
            actor_id=actor_id, metadata_=metadata, prev_hash=prev_hash, event_hash=event_hash,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def verify_chain(self, organization_id: uuid.UUID) -> dict:
        events = (
            self.db.query(ConsentEvent)
            .filter(ConsentEvent.organization_id == organization_id)
            .order_by(ConsentEvent.created_at.asc(), ConsentEvent.id.asc())
            .all()
        )
        prev_hash = GENESIS_HASH
        for event in events:
            payload = build_event_payload(
                event.consent_id, event.data_subject_id, event.organization_id,
                event.event_type, event.old_status, event.new_status,
                event.actor_type, event.actor_id, event.metadata_ or {},
            )
            expected = compute_event_hash(prev_hash, payload)
            if event.prev_hash != prev_hash or event.event_hash != expected:
                return {
                    "intact": False, "events_checked": len(events),
                    "broken_event_id": str(event.id),
                    "message": "Hash chain broken at this event",
                }
            prev_hash = event.event_hash
        return {"intact": True, "events_checked": len(events), "broken_event_id": None, "message": "Chain intact"}
