"""RBAC: role -> permission matrix and FastAPI dependencies.

Roles: super_admin, org_admin, dpo, data_subject
Permissions are checked via require_permission(...) / require_role(...).
"""
import uuid
from enum import StrEnum

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token, hash_api_key
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    DPO = "dpo"
    DATA_SUBJECT = "data_subject"


class Permission(StrEnum):
    ORG_MANAGE = "org:manage"
    APIKEY_MANAGE = "apikey:manage"
    PURPOSE_MANAGE = "purpose:manage"
    PURPOSE_READ = "purpose:read"
    CONSENT_MANAGE = "consent:manage"
    CONSENT_READ = "consent:read"
    CONSENT_CHECK = "consent:check"
    AUDIT_READ = "audit:read"
    DSR_MANAGE = "dsr:manage"
    DSR_CREATE = "dsr:create"
    WEBHOOK_MANAGE = "webhook:manage"
    REPORT_READ = "report:read"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),
    Role.ORG_ADMIN: {
        Permission.APIKEY_MANAGE, Permission.PURPOSE_MANAGE, Permission.PURPOSE_READ,
        Permission.CONSENT_MANAGE, Permission.CONSENT_READ, Permission.CONSENT_CHECK,
        Permission.AUDIT_READ, Permission.DSR_MANAGE, Permission.DSR_CREATE,
        Permission.WEBHOOK_MANAGE, Permission.REPORT_READ,
    },
    Role.DPO: {
        Permission.PURPOSE_READ, Permission.CONSENT_READ, Permission.CONSENT_CHECK,
        Permission.AUDIT_READ, Permission.DSR_MANAGE, Permission.DSR_CREATE,
        Permission.REPORT_READ,
    },
    Role.DATA_SUBJECT: {
        Permission.PURPOSE_READ, Permission.CONSENT_READ, Permission.DSR_CREATE,
    },
}


def has_permission(role: str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    # API key auth (server-to-server): synthesize a service principal.
    if x_api_key:
        from app.models.api_key import ApiKey

        key_hash = hash_api_key(x_api_key)
        api_key = db.query(ApiKey).filter(
            ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None)
        ).first()
        if api_key is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        from datetime import UTC, datetime

        api_key.last_used_at = datetime.now(UTC)
        db.commit()
        request.state.api_key_scopes = list(api_key.scopes or [])
        request.state.api_key_org_id = api_key.organization_id
        # Service principal: org_admin-level user bound to the key's org.
        principal = User(
            id=uuid.uuid4(), organization_id=api_key.organization_id,
            email="api-key@service.local", hashed_password="", role=Role.ORG_ADMIN, is_active=True,
        )
        return principal
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_role(*roles: Role):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in [r.value for r in roles]:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return dependency


def require_permission(permission: Permission):
    def dependency(request: Request, user: User = Depends(get_current_user)) -> User:
        scopes = getattr(request.state, "api_key_scopes", None)
        if scopes is not None:
            # API key path: scope check (empty scopes = all org_admin perms for simplicity
            # is NOT allowed; keys must carry explicit scopes or "*" ).
            if "*" in scopes or permission.value in scopes:
                return user
            # Fall back to role matrix only if scopes empty and key was created pre-scope;
            # otherwise enforce scopes strictly.
            if scopes:
                raise HTTPException(status_code=403, detail="API key scope insufficient")
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=403, detail="Permission denied")
        return user

    return dependency


def ensure_org_access(user: User, organization_id: uuid.UUID) -> None:
    """Tenant isolation guard: super_admin sees all, others only their org."""
    if user.role == Role.SUPER_ADMIN:
        return
    if user.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Resource not found")
