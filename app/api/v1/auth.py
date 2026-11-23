import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.middleware.rate_limit import rate_limit
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201, dependencies=[Depends(rate_limit(20))])
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    org = db.query(Organization).filter(Organization.slug == payload.organization_slug).first()
    if org is None:
        org = Organization(name=payload.organization_name, slug=payload.organization_slug)
        db.add(org)
        db.flush()
    existing = db.query(User).filter(User.organization_id == org.id, User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already exists in this organization")
    user = User(
        organization_id=org.id, email=payload.email,
        hashed_password=hash_password(payload.password), role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit(20))])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    org = db.query(Organization).filter(Organization.slug == payload.organization_slug).first()
    if org is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = db.query(User).filter(User.organization_id == org.id, User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        claims = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
