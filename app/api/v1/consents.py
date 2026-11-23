import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.db.session import get_db
from app.middleware.rate_limit import rate_limit
from app.models.consent import Consent
from app.models.consent_event import ConsentEvent
from app.models.data_subject import DataSubject
from app.models.purpose import Purpose
from app.models.user import User
from app.schemas.consent import (
    ConsentCheckRequest,
    ConsentCheckResponse,
    ConsentEventOut,
    ConsentGrantRequest,
    ConsentOut,
)
from app.services.consent_service import ConsentService

router = APIRouter(tags=["consents"])


@router.post("/consents", response_model=list[ConsentOut], status_code=201, dependencies=[Depends(rate_limit(120))])
def grant_consent(payload: ConsentGrantRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.CONSENT_MANAGE))) -> list[Consent]:
    ip = request.client.host if request.client else None
    return ConsentService(db).grant(
        user.organization_id, payload.external_ref, payload.email, payload.purposes,
        payload.source, str(user.id), ip_address=ip, user_agent=request.headers.get("user-agent"),
    )


@router.post("/consents/{consent_id}/withdraw", response_model=ConsentOut)
def withdraw_consent(consent_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.CONSENT_MANAGE))) -> Consent:
    return ConsentService(db).withdraw(consent_id, user.organization_id, str(user.id))


@router.post("/consents/check", response_model=ConsentCheckResponse, dependencies=[Depends(rate_limit(120))])
def check_consent(payload: ConsentCheckRequest, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.CONSENT_CHECK))) -> ConsentCheckResponse:
    subject = None
    if payload.data_subject_id is not None:
        subject = db.get(DataSubject, payload.data_subject_id)
        if subject is not None and subject.organization_id != user.organization_id:
            subject = None
    elif payload.external_ref:
        subject = (
            db.query(DataSubject)
            .filter(DataSubject.organization_id == user.organization_id, DataSubject.external_ref == payload.external_ref)
            .first()
        )
    if subject is None:
        return ConsentCheckResponse(has_consent=False, status=None, purpose_code=payload.purpose_code)
    consent = ConsentService(db).check(user.organization_id, subject.id, payload.purpose_code)
    if consent is None:
        return ConsentCheckResponse(has_consent=False, status=None, purpose_code=payload.purpose_code)
    return ConsentCheckResponse(
        has_consent=True, status=consent.status, purpose_code=payload.purpose_code, expires_at=consent.expires_at,
    )


@router.get("/data-subjects/{subject_id}/consents")
def subject_consents(subject_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.CONSENT_READ))) -> list[dict]:
    subject = db.get(DataSubject, subject_id)
    if subject is None or subject.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Data subject not found")
    consents = db.query(Consent).filter(Consent.data_subject_id == subject_id).all()
    purposes = {str(p.id): p for p in db.query(Purpose).filter(Purpose.organization_id == user.organization_id).all()}
    return [
        {
            "id": str(c.id), "purpose_id": str(c.purpose_id),
            "purpose_code": (purposes[str(c.purpose_id)].code if str(c.purpose_id) in purposes else None),
            "status": c.status,
            "granted_at": c.granted_at.isoformat() if c.granted_at else None,
            "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        }
        for c in consents
    ]


@router.get("/data-subjects/{subject_id}/consents/history", response_model=list[ConsentEventOut])
def subject_history(subject_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.CONSENT_READ))) -> list[ConsentEvent]:
    subject = db.get(DataSubject, subject_id)
    if subject is None or subject.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Data subject not found")
    return list(
        db.query(ConsentEvent)
        .filter(ConsentEvent.data_subject_id == subject_id, ConsentEvent.organization_id == user.organization_id)
        .order_by(ConsentEvent.created_at.asc())
        .all()
    )


@router.get("/data-subjects")
def list_subjects(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.CONSENT_READ))) -> list[dict]:
    subjects = db.query(DataSubject).filter(DataSubject.organization_id == user.organization_id).limit(200).all()
    return [
        {"id": str(s.id), "external_ref": s.external_ref, "email": s.email, "is_anonymized": s.is_anonymized}
        for s in subjects
    ]
