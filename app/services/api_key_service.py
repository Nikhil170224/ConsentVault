import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import generate_api_key, verify_api_key
from app.models.api_key import ApiKey


class ApiKeyService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, organization_id: uuid.UUID, name: str, scopes: list[str]) -> tuple[ApiKey, str]:
        raw, prefix, key_hash = generate_api_key()
        api_key = ApiKey(
            organization_id=organization_id, name=name, key_prefix=prefix,
            key_hash=key_hash, scopes=scopes or ["*"],
        )
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key, raw

    def revoke(self, key_id: uuid.UUID, organization_id: uuid.UUID) -> ApiKey:
        api_key = self.db.get(ApiKey, key_id)
        if api_key is None or api_key.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="API key not found")
        api_key.revoked_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def verify(self, raw_key: str) -> ApiKey | None:
        from app.core.security import hash_api_key

        candidate = self.db.query(ApiKey).filter(
            ApiKey.key_hash == hash_api_key(raw_key), ApiKey.revoked_at.is_(None)
        ).first()
        if candidate is None:
            return None
        if not verify_api_key(raw_key, candidate.key_hash):
            return None
        return candidate
