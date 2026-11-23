"""Seed realistic ConsentVault data.

Default (full spec scale): 3 organizations, 50K+ data subjects, 300K+ consent
events, 5K DSRs. Use --scale 0.01 for a quick local smoke seed (~500 subjects).

Usage:
    python scripts/seed_data.py [--scale 1.0] [--database-url URL]
"""
import argparse
import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.base import Base
from app.models import *  # noqa: F401,F403
from app.models.consent import Consent
from app.models.data_subject import DataSubject
from app.models.dsr import DsrRequest
from app.models.organization import Organization
from app.models.purpose import Purpose
from app.models.user import User
from app.services.audit_service import AuditService

fake = Faker()
random.seed(42)
Faker.seed(42)

PURPOSE_CODES = ["marketing", "analytics", "personalization", "third_party_sharing"]
DSR_TYPES = ["ACCESS", "EXPORT", "DELETE", "CORRECTION"]
DSR_STATUSES = ["RECEIVED", "VERIFYING", "IN_PROGRESS", "COMPLETED", "REJECTED"]
DSR_WEIGHTS = [0.25, 0.20, 0.25, 0.25, 0.05]


def seed(database_url: str, scale: float) -> dict:
    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    n_subjects = max(int(50_000 * scale), 30)
    n_dsrs = max(int(5_000 * scale), 10)
    stats = {"organizations": 0, "subjects": 0, "consents": 0, "events": 0, "dsrs": 0}
    audit = AuditService(session)
    now = datetime.now(UTC)

    orgs: list[Organization] = []
    for i in range(3):
        org = Organization(name=fake.company(), slug=f"seed-org-{i + 1}-{uuid.uuid4().hex[:6]}")
        session.add(org)
        session.flush()
        orgs.append(org)
        session.add(User(
            organization_id=org.id, email=f"admin{i + 1}@example.com",
            hashed_password=hash_password("Password123!"), role="org_admin",
        ))
        stats["organizations"] += 1
    session.commit()

    purposes_by_org: dict[uuid.UUID, list[Purpose]] = {}
    for org in orgs:
        plist = []
        for code in PURPOSE_CODES:
            p = Purpose(
                organization_id=org.id, code=code, name=code.replace("_", " ").title(),
                description=f"Consent for {code}", legal_basis="CONSENT",
                is_required=(code == "analytics"), retention_days=365, version=1,
            )
            session.add(p)
            plist.append(p)
        purposes_by_org[org.id] = plist
    session.flush()

    # Bulk-create subjects in batches.
    subjects: list[DataSubject] = []
    per_org = n_subjects // 3
    for org in orgs:
        for j in range(per_org):
            subjects.append(DataSubject(
                organization_id=org.id,
                external_ref=f"subject-{org.slug}-{j}",
                email=fake.email(),
            ))
    session.add_all(subjects)
    session.commit()
    stats["subjects"] = len(subjects)

    # Consents + hash-chained events. ~2 purposes per subject => events >= 2x subjects.
    consent_rows: list[Consent] = []
    for subject in subjects:
        chosen = random.sample(purposes_by_org[subject.organization_id], k=2)
        for purpose in chosen:
            granted_at = now - timedelta(days=random.randint(1, 180))
            status = "GRANTED" if random.random() < 0.85 else "WITHDRAWN"
            consent_rows.append(Consent(
                data_subject_id=subject.id, purpose_id=purpose.id, status=status,
                granted_at=granted_at,
                withdrawn_at=(granted_at + timedelta(days=random.randint(1, 30))) if status == "WITHDRAWN" else None,
                source=random.choice(["web", "mobile", "api"]),
            ))
    session.add_all(consent_rows)
    session.commit()
    stats["consents"] = len(consent_rows)

    for consent in consent_rows:
        subject = next(s for s in subjects if s.id == consent.data_subject_id)
        audit.record_event(
            consent.id, consent.data_subject_id, subject.organization_id,
            "consent.granted", None, "GRANTED", actor_type="system",
            metadata={"seed": True},
        )
        stats["events"] += 1
        if consent.status == "WITHDRAWN":
            audit.record_event(
                consent.id, consent.data_subject_id, subject.organization_id,
                "consent.withdrawn", "GRANTED", "WITHDRAWN", actor_type="system",
                metadata={"seed": True},
            )
            stats["events"] += 1
        if stats["events"] % 5000 == 0:
            session.commit()
    session.commit()

    for _ in range(n_dsrs):
        subject = random.choice(subjects)
        status = random.choices(DSR_STATUSES, weights=DSR_WEIGHTS)[0]
        created = now - timedelta(days=random.randint(0, 60))
        session.add(DsrRequest(
            organization_id=subject.organization_id, data_subject_id=subject.id,
            type=random.choice(DSR_TYPES), status=status,
            due_date=created + timedelta(days=30),
            completed_at=(created + timedelta(days=random.randint(1, 25))) if status == "COMPLETED" else None,
        ))
    session.commit()
    stats["dsrs"] = n_dsrs
    session.close()
    engine.dispose()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ConsentVault data")
    parser.add_argument("--scale", type=float, default=1.0, help="1.0 = full spec scale")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql+psycopg://consentvault:consentvault@localhost:5432/consentvault"),
    )
    args = parser.parse_args()
    stats = seed(args.database_url, args.scale)
    print("Seed complete:", stats)


if __name__ == "__main__":
    main()
