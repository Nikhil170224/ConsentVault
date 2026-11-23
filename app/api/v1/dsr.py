import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.db.session import get_db
from app.models.data_subject import DataSubject
from app.models.dsr import DsrRequest, DsrStatusHistory
from app.models.user import User
from app.repositories.consent_repo import get_or_create_subject
from app.schemas.dsr import DsrCreate, DsrOut, DsrStatusUpdate
from app.services.dsr_service import DsrService
from app.services.export_service import ExportService

router = APIRouter(prefix="/dsr", tags=["dsr"])


@router.post("", response_model=DsrOut, status_code=201)
def create_dsr(payload: DsrCreate, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.DSR_CREATE))) -> DsrRequest:
    if payload.data_subject_id is not None:
        subject = db.get(DataSubject, payload.data_subject_id)
        if subject is None or subject.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Data subject not found")
    elif payload.external_ref:
        subject = get_or_create_subject(db, user.organization_id, payload.external_ref, None)
        db.commit()
    else:
        raise HTTPException(status_code=422, detail="Provide data_subject_id or external_ref")
    return DsrService(db).create(user.organization_id, subject.id, payload.type, payload.details, str(user.id))


@router.get("", response_model=list[DsrOut])
def list_dsr(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.DSR_MANAGE))) -> list[DsrRequest]:
    return list(
        db.query(DsrRequest)
        .filter(DsrRequest.organization_id == user.organization_id)
        .order_by(DsrRequest.created_at.desc())
        .limit(200)
        .all()
    )


@router.get("/overdue", response_model=list[DsrOut])
def overdue_dsr(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.DSR_MANAGE))) -> list[DsrRequest]:
    return DsrService(db).overdue(user.organization_id)


@router.get("/{dsr_id}", response_model=DsrOut)
def get_dsr(dsr_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.DSR_MANAGE))) -> DsrRequest:
    dsr = db.get(DsrRequest, dsr_id)
    if dsr is None or dsr.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="DSR not found")
    return dsr


@router.patch("/{dsr_id}/status", response_model=DsrOut)
def update_dsr_status(dsr_id: uuid.UUID, payload: DsrStatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.DSR_MANAGE))) -> DsrRequest:
    dsr = db.get(DsrRequest, dsr_id)
    if dsr is None or dsr.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="DSR not found")
    return DsrService(db).transition(dsr, payload.status, str(user.id), note=payload.note, rejection_reason=payload.rejection_reason)


@router.get("/{dsr_id}/history")
def dsr_history(dsr_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.DSR_MANAGE))) -> list[dict]:
    dsr = db.get(DsrRequest, dsr_id)
    if dsr is None or dsr.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="DSR not found")
    rows = db.query(DsrStatusHistory).filter(DsrStatusHistory.dsr_id == dsr_id).order_by(DsrStatusHistory.created_at.asc()).all()
    return [
        {"from_status": r.from_status, "to_status": r.to_status, "changed_by": r.changed_by, "note": r.note,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


@router.get("/{dsr_id}/download")
def download_dsr(dsr_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.DSR_MANAGE))) -> JSONResponse:
    dsr = db.get(DsrRequest, dsr_id)
    if dsr is None or dsr.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="DSR not found")
    if dsr.type not in ("ACCESS", "EXPORT"):
        raise HTTPException(status_code=400, detail="Download only available for ACCESS/EXPORT requests")
    if dsr.result_data is not None:
        bundle = dsr.result_data
    else:
        subject = db.get(DataSubject, dsr.data_subject_id)
        if subject is None:
            raise HTTPException(status_code=404, detail="Data subject not found")
        bundle = ExportService(db).build_bundle(subject)
    return JSONResponse(
        content=bundle,
        headers={"Content-Disposition": f'attachment; filename="dsr-export-{dsr.id}.json"'},
    )
