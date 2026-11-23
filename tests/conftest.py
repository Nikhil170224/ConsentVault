import os
import uuid

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://consentvault:consentvault@localhost:5432/consentvault_test",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.middleware.rate_limit import limiter
from app.models import *  # noqa: F401,F403  register models

TEST_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_URL, pool_pre_ping=True)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

TRIGGER_DDL = [
    """
    CREATE OR REPLACE FUNCTION consent_events_append_only()
    RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'consent_events is append-only: % not allowed', TG_OP;
    END;
    $$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS trg_consent_events_no_update ON consent_events;",
    "DROP TRIGGER IF EXISTS trg_consent_events_no_delete ON consent_events;",
    "CREATE TRIGGER trg_consent_events_no_update BEFORE UPDATE ON consent_events FOR EACH ROW EXECUTE FUNCTION consent_events_append_only();",
    "CREATE TRIGGER trg_consent_events_no_delete BEFORE DELETE ON consent_events FOR EACH ROW EXECUTE FUNCTION consent_events_append_only();",
]


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for stmt in TRIGGER_DDL:
            conn.execute(text(stmt))
        conn.commit()
    limiter.reset()
    get_settings.cache_clear()
    yield


@pytest.fixture()
def db_session():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client: TestClient, slug: str, email: str, role: str = "org_admin", password: str = "Password123!") -> dict:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": slug.title(), "organization_slug": slug,
            "email": email, "password": password, "role": role,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_org_user(client: TestClient, slug: str | None = None, role: str = "org_admin"):
    slug = slug or f"org-{uuid.uuid4().hex[:8]}"
    email = f"admin-{uuid.uuid4().hex[:6]}@example.com"
    tokens = register(client, slug, email, role=role)
    headers = auth_headers(tokens["access_token"])
    me = client.get("/api/v1/auth/me", headers=headers).json()
    return {"slug": slug, "email": email, "tokens": tokens, "headers": headers, "me": me, "org_id": me["organization_id"]}


def make_purpose(client: TestClient, headers: dict, code: str = "marketing", is_required: bool = False) -> dict:
    resp = client.post(
        "/api/v1/purposes", headers=headers,
        json={"code": code, "name": code.title(), "description": f"{code} purpose",
              "legal_basis": "CONSENT", "is_required": is_required, "retention_days": 365},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def grant(client: TestClient, headers: dict, external_ref: str, purpose_code: str = "marketing", **kw):
    body = {"external_ref": external_ref, "email": f"{external_ref}@example.com",
            "purposes": [{"purpose_code": purpose_code}], "source": "web"}
    body.update(kw)
    return client.post("/api/v1/consents", headers=headers, json=body)
