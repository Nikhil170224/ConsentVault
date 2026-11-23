import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import sign_webhook_payload
from app.models.webhook import WebhookDelivery, WebhookEndpoint

logger = get_logger("consentvault.webhooks")
MAX_ATTEMPTS = 5


def backoff_seconds(attempt: int) -> int:
    """Exponential backoff: 2, 4, 8, 16, 32 seconds."""
    return 2 ** max(attempt, 1)


class WebhookService:
    def __init__(self, db: Session):
        self.db = db

    def dispatch(self, organization_id: uuid.UUID, event_type: str, data: dict) -> list[WebhookDelivery]:
        endpoints = (
            self.db.query(WebhookEndpoint)
            .filter(WebhookEndpoint.organization_id == organization_id, WebhookEndpoint.is_active.is_(True))
            .all()
        )
        deliveries: list[WebhookDelivery] = []
        for ep in endpoints:
            if ep.events and event_type not in ep.events:
                continue
            payload = {"event": event_type, "data": data}
            delivery = WebhookDelivery(
                endpoint_id=ep.id, event_type=event_type, payload=payload, status="PENDING", attempts=0,
            )
            self.db.add(delivery)
            self.db.flush()
            self.attempt_delivery(delivery, ep)
            deliveries.append(delivery)
        self.db.commit()
        return deliveries

    def attempt_delivery(self, delivery: WebhookDelivery, endpoint: WebhookEndpoint) -> WebhookDelivery:
        body = json.dumps(delivery.payload, sort_keys=True).encode("utf-8")
        signature = sign_webhook_payload(body, endpoint.secret)
        delivery.attempts += 1
        try:
            with httpx.Client(timeout=5.0, trust_env=False) as client:
                resp = client.post(
                    endpoint.url, content=body,
                    headers={"Content-Type": "application/json", "X-ConsentVault-Signature": signature},
                )
            if 200 <= resp.status_code < 300:
                delivery.status = "DELIVERED"
                delivery.last_error = None
                delivery.next_retry_at = None
            else:
                delivery.last_error = f"HTTP {resp.status_code}"
                self._schedule_retry(delivery)
        except Exception as exc:  # network errors etc.
            delivery.last_error = str(exc)[:500]
            self._schedule_retry(delivery)
        self.db.flush()
        return delivery

    def _schedule_retry(self, delivery: WebhookDelivery) -> None:
        if delivery.attempts >= MAX_ATTEMPTS:
            delivery.status = "FAILED"
            delivery.next_retry_at = None
        else:
            delivery.status = "PENDING"
            delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff_seconds(delivery.attempts))

    def retry_pending(self) -> int:
        now = datetime.now(UTC)
        pending = (
            self.db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.status == "PENDING",
                WebhookDelivery.attempts < MAX_ATTEMPTS,
                (WebhookDelivery.next_retry_at.is_(None)) | (WebhookDelivery.next_retry_at <= now),
            )
            .all()
        )
        count = 0
        for delivery in pending:
            endpoint = self.db.get(WebhookEndpoint, delivery.endpoint_id)
            if endpoint is None:
                continue
            self.attempt_delivery(delivery, endpoint)
            count += 1
        self.db.commit()
        return count
