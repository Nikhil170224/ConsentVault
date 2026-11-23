from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.db.session import get_db
from app.models.consent_event import ConsentEvent
from app.models.user import User
from app.schemas.consent import ConsentEventOut
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/verify-chain")
def verify_chain(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.AUDIT_READ))) -> dict:
    return AuditService(db).verify_chain(user.organization_id)


@router.get("/events", response_model=list[ConsentEventOut])
def list_events(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.AUDIT_READ))) -> list[ConsentEvent]:
    return list(
        db.query(ConsentEvent)
        .filter(ConsentEvent.organization_id == user.organization_id)
        .order_by(ConsentEvent.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
