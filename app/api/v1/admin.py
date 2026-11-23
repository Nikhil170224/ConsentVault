from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.db.session import get_db
from app.models.user import User
from app.services.consent_service import ConsentService

router = APIRouter(tags=["admin"])
SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def run_report(db: Session, filename: str, org_id) -> list[dict]:
    sql = (SQL_DIR / filename).read_text(encoding="utf-8")
    result = db.execute(text(sql), {"org_id": str(org_id)})
    return [dict(row._mapping) for row in result]


@router.post("/admin/sweep-expired")
def sweep_expired(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.CONSENT_MANAGE))) -> dict:
    return {"expired_count": ConsentService(db).sweep_expired()}


@router.get("/reports/consent-rates")
def consent_rates(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.REPORT_READ))) -> list[dict]:
    return run_report(db, "consent_rates.sql", user.organization_id)


@router.get("/reports/withdrawal-trends")
def withdrawal_trends(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.REPORT_READ))) -> list[dict]:
    return run_report(db, "withdrawal_trends.sql", user.organization_id)


@router.get("/reports/dsr-sla")
def dsr_sla(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.REPORT_READ))) -> list[dict]:
    return run_report(db, "dsr_sla.sql", user.organization_id)
