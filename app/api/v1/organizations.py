import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import Permission, Role, ensure_org_access, require_permission, require_role
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import ApiKeyCreate, ApiKeyCreatedOut, ApiKeyOut, OrganizationCreate, OrganizationOut
from app.services.api_key_service import ApiKeyService

router = APIRouter(tags=["organizations"])


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
def create_organization(
    payload: OrganizationCreate, db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.SUPER_ADMIN)),
) -> Organization:
    if db.query(Organization).filter(Organization.slug == payload.slug).first():
        raise HTTPException(status_code=409, detail="Slug already taken")
    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(db: Session = Depends(get_db), user: User = Depends(require_role(Role.SUPER_ADMIN))) -> list[Organization]:
    return list(db.query(Organization).order_by(Organization.created_at.desc()).all())


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
def get_organization(org_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.PURPOSE_READ))) -> Organization:
    ensure_org_access(user, org_id)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.post("/organizations/{org_id}/api-keys", response_model=ApiKeyCreatedOut, status_code=201)
def create_api_key(org_id: uuid.UUID, payload: ApiKeyCreate, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.APIKEY_MANAGE))) -> ApiKeyCreatedOut:
    ensure_org_access(user, org_id)
    if db.get(Organization, org_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    api_key, raw = ApiKeyService(db).create(org_id, payload.name, payload.scopes)
    return ApiKeyCreatedOut(
        id=api_key.id, organization_id=api_key.organization_id, name=api_key.name,
        key_prefix=api_key.key_prefix, scopes=list(api_key.scopes or []),
        last_used_at=api_key.last_used_at, revoked_at=api_key.revoked_at,
        created_at=api_key.created_at, raw_key=raw,
    )


@router.get("/organizations/{org_id}/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(org_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.APIKEY_MANAGE))) -> list[ApiKey]:
    ensure_org_access(user, org_id)
    return list(db.query(ApiKey).filter(ApiKey.organization_id == org_id).all())


@router.delete("/organizations/{org_id}/api-keys/{key_id}", response_model=ApiKeyOut)
def revoke_api_key(org_id: uuid.UUID, key_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.APIKEY_MANAGE))) -> ApiKey:
    ensure_org_access(user, org_id)
    return ApiKeyService(db).revoke(key_id, org_id)
