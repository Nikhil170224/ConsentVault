import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
API_KEY_PREFIX = "cv_"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    s = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=s.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.secret_key, algorithm=s.algorithm)


def create_refresh_token(subject: str) -> str:
    s = get_settings()
    expire = datetime.now(UTC) + timedelta(days=s.refresh_token_expire_days)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, s.secret_key, algorithm=s.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        return jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def generate_api_key() -> tuple[str, str, str]:
    """Return (raw_key, key_prefix, key_hash). Raw key is shown once."""
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    prefix = raw[:12]
    return raw, prefix, hash_api_key(raw)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(raw_key), stored_hash)


def sign_webhook_payload(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_webhook_signature(payload: bytes, secret: str, signature: str) -> bool:
    return hmac.compare_digest(sign_webhook_payload(payload, secret), signature)


def hash_pii(value: str) -> str:
    """Irreversible hash used for anonymization."""
    return "anon_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
