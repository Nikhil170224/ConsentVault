import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.db.session import get_db
from app.models.purpose import Purpose
from app.models.user import User
from app.schemas.purpose import PurposeCreate, PurposeOut, PurposeUpdate

router = APIRouter(prefix="/purposes", tags=["purposes"])


@router.post("", response_model=PurposeOut, status_code=201)
def create_purpose(payload: PurposeCreate, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.PURPOSE_MANAGE))) -> Purpose:
    existing = (
        db.query(Purpose)
        .filter(Purpose.organization_id == user.organization_id, Purpose.code == payload.code)
        .order_by(Purpose.version.desc())
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Purpose code already exists; use PATCH to create a new version")
    purpose = Purpose(organization_id=user.organization_id, **payload.model_dump(), version=1)
    db.add(purpose)
    db.commit()
    db.refresh(purpose)
    return purpose


@router.get("", response_model=list[PurposeOut])
def list_purposes(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.PURPOSE_READ))) -> list[Purpose]:
    return list(
        db.query(Purpose)
        .filter(Purpose.organization_id == user.organization_id)
        .order_by(Purpose.code, Purpose.version.desc())
        .all()
    )


@router.get("/{purpose_id}", response_model=PurposeOut)
def get_purpose(purpose_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.PURPOSE_READ))) -> Purpose:
    purpose = db.get(Purpose, purpose_id)
    if purpose is None or purpose.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Purpose not found")
    return purpose


@router.patch("/{purpose_id}", response_model=PurposeOut)
def update_purpose(purpose_id: uuid.UUID, payload: PurposeUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.PURPOSE_MANAGE))) -> Purpose:
    """Versioning: changing description/legal_basis creates a NEW version row.

    Existing consents keep pointing at the version the subject agreed to.
    Other fields update in place on the latest version.
    """
    purpose = db.get(Purpose, purpose_id)
    if purpose is None or purpose.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Purpose not found")
    updates = payload.model_dump(exclude_unset=True)
    versioned = (
        ("description" in updates and updates["description"] != purpose.description)
        or ("legal_basis" in updates and updates["legal_basis"] != purpose.legal_basis)
    )
    if versioned:
        new_version = Purpose(
            organization_id=purpose.organization_id, code=purpose.code,
            name=updates.get("name", purpose.name),
            description=updates.get("description", purpose.description),
            legal_basis=updates.get("legal_basis", purpose.legal_basis),
            is_required=updates.get("is_required", purpose.is_required),
            retention_days=updates.get("retention_days", purpose.retention_days),
            version=purpose.version + 1, is_active=True,
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)
        return new_version
    for key, value in updates.items():
        setattr(purpose, key, value)
    db.commit()
    db.refresh(purpose)
    return purpose


@router.delete("/{purpose_id}")
def delete_purpose(purpose_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.PURPOSE_MANAGE))) -> dict:
    purpose = db.get(Purpose, purpose_id)
    if purpose is None or purpose.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Purpose not found")
    purpose.is_active = False
    db.commit()
    return {"detail": "Purpose deactivated"}
