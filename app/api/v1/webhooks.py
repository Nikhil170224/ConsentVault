import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.db.session import get_db
from app.models.user import User
from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.schemas.webhook import WebhookCreate, WebhookOut, WebhookUpdate
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookOut, status_code=201)
def create_webhook(payload: WebhookCreate, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.WEBHOOK_MANAGE))) -> WebhookEndpoint:
    ep = WebhookEndpoint(
        organization_id=user.organization_id, url=payload.url, secret=payload.secret, events=payload.events,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@router.get("", response_model=list[WebhookOut])
def list_webhooks(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.WEBHOOK_MANAGE))) -> list[WebhookEndpoint]:
    return list(db.query(WebhookEndpoint).filter(WebhookEndpoint.organization_id == user.organization_id).all())


@router.patch("/{endpoint_id}", response_model=WebhookOut)
def update_webhook(endpoint_id: uuid.UUID, payload: WebhookUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.WEBHOOK_MANAGE))) -> WebhookEndpoint:
    ep = db.get(WebhookEndpoint, endpoint_id)
    if ep is None or ep.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(ep, key, value)
    db.commit()
    db.refresh(ep)
    return ep


@router.delete("/{endpoint_id}")
def delete_webhook(endpoint_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.WEBHOOK_MANAGE))) -> dict:
    ep = db.get(WebhookEndpoint, endpoint_id)
    if ep is None or ep.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    db.delete(ep)
    db.commit()
    return {"detail": "Webhook endpoint deleted"}


@router.get("/{endpoint_id}/deliveries")
def list_deliveries(endpoint_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.WEBHOOK_MANAGE))) -> list[dict]:
    ep = db.get(WebhookEndpoint, endpoint_id)
    if ep is None or ep.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    rows = db.query(WebhookDelivery).filter(WebhookDelivery.endpoint_id == endpoint_id).order_by(WebhookDelivery.created_at.desc()).limit(100).all()
    return [
        {"id": str(r.id), "event_type": r.event_type, "status": r.status, "attempts": r.attempts, "last_error": r.last_error}
        for r in rows
    ]


@router.post("/retry-pending")
def retry_pending(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.WEBHOOK_MANAGE))) -> dict:
    return {"retried": WebhookService(db).retry_pending()}
