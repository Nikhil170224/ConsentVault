from datetime import UTC, datetime, timedelta

import httpx
import respx
from sqlalchemy import text

from tests.conftest import grant, make_org_user, make_purpose


def _create_dsr(client, headers, dsr_type="EXPORT", external_ref="user-1"):
    resp = client.post("/api/v1/dsr", headers=headers,
                       json={"external_ref": external_ref, "type": dsr_type})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _advance(client, headers, dsr_id, *statuses):
    last = None
    for status in statuses:
        last = client.patch(f"/api/v1/dsr/{dsr_id}/status", headers=headers, json={"status": status})
        assert last.status_code == 200, last.text
    return last.json()


def test_dsr_happy_path_and_export_download(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    grant(client, ctx["headers"], "user-1")
    dsr = _create_dsr(client, ctx["headers"])
    assert dsr["status"] == "RECEIVED"
    assert dsr["due_date"] is not None
    done = _advance(client, ctx["headers"], dsr["id"], "VERIFYING", "IN_PROGRESS", "COMPLETED")
    assert done["status"] == "COMPLETED"
    assert done["completed_at"] is not None
    download = client.get(f"/api/v1/dsr/{dsr['id']}/download", headers=ctx["headers"])
    assert download.status_code == 200
    bundle = download.json()
    assert bundle["data_subject"]["external_ref"] == "user-1"
    assert len(bundle["consents"]) == 1
    assert len(bundle["consent_history"]) >= 1
    assert len(bundle["dsr_requests"]) == 1
    history = client.get(f"/api/v1/dsr/{dsr['id']}/history", headers=ctx["headers"]).json()
    assert [h["to_status"] for h in history] == ["RECEIVED", "VERIFYING", "IN_PROGRESS", "COMPLETED"]


def test_dsr_illegal_transition_422(client):
    ctx = make_org_user(client)
    dsr = _create_dsr(client, ctx["headers"])
    resp = client.patch(f"/api/v1/dsr/{dsr['id']}/status", headers=ctx["headers"],
                        json={"status": "COMPLETED"})
    assert resp.status_code == 422


def test_dsr_delete_anonymizes_but_chain_stays_valid(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    consent = grant(client, ctx["headers"], "user-1").json()[0]
    subject_id = consent["data_subject_id"]
    dsr = _create_dsr(client, ctx["headers"], dsr_type="DELETE")
    _advance(client, ctx["headers"], dsr["id"], "VERIFYING", "IN_PROGRESS", "COMPLETED")
    subjects = client.get("/api/v1/data-subjects", headers=ctx["headers"]).json()
    subject = [s for s in subjects if s["id"] == subject_id][0]
    assert subject["is_anonymized"] is True
    assert subject["external_ref"].startswith("anon_")
    assert "user-1@example.com" not in (subject["email"] or "")
    verify = client.get("/api/v1/audit/verify-chain", headers=ctx["headers"]).json()
    assert verify["intact"] is True


def test_dsr_overdue(client, db_session):
    ctx = make_org_user(client)
    dsr = _create_dsr(client, ctx["headers"])
    past = datetime.now(UTC) - timedelta(days=1)
    db_session.execute(
        text("UPDATE dsr_requests SET due_date = :d WHERE id = :i"),
        {"d": past, "i": dsr["id"]},
    )
    db_session.commit()
    overdue = client.get("/api/v1/dsr/overdue", headers=ctx["headers"]).json()
    assert [d["id"] for d in overdue] == [dsr["id"]]


@respx.mock
def test_webhook_delivery_and_signature(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    route = respx.post("https://hooks.example.com/cv").mock(return_value=httpx.Response(200))
    created = client.post("/api/v1/webhooks", headers=ctx["headers"], json={
        "url": "https://hooks.example.com/cv", "secret": "whsec_testsecret",
        "events": ["consent.granted"],
    })
    assert created.status_code == 201, created.text
    assert "secret" not in created.json()
    grant(client, ctx["headers"], "user-1")
    assert route.called
    request = route.calls.last.request
    assert "X-ConsentVault-Signature" in request.headers
    deliveries = client.get(f"/api/v1/webhooks/{created.json()['id']}/deliveries",
                            headers=ctx["headers"]).json()
    assert deliveries[0]["status"] == "DELIVERED"
    assert deliveries[0]["attempts"] == 1


@respx.mock
def test_webhook_retry_on_failure(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    route = respx.post("https://hooks.example.com/fail").mock(return_value=httpx.Response(500))
    created = client.post("/api/v1/webhooks", headers=ctx["headers"], json={
        "url": "https://hooks.example.com/fail", "secret": "whsec_testsecret",
        "events": ["consent.granted"],
    }).json()
    grant(client, ctx["headers"], "user-1")
    deliveries = client.get(f"/api/v1/webhooks/{created['id']}/deliveries",
                            headers=ctx["headers"]).json()
    assert deliveries[0]["status"] == "PENDING"
    assert deliveries[0]["attempts"] == 1
    assert deliveries[0]["last_error"] == "HTTP 500"
    assert route.call_count == 1


def test_reports_endpoints(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    consent = grant(client, ctx["headers"], "user-1").json()[0]
    client.post(f"/api/v1/consents/{consent['id']}/withdraw", headers=ctx["headers"])
    _create_dsr(client, ctx["headers"])
    for path in ("/api/v1/reports/consent-rates", "/api/v1/reports/withdrawal-trends", "/api/v1/reports/dsr-sla"):
        resp = client.get(path, headers=ctx["headers"])
        assert resp.status_code == 200, f"{path}: {resp.text}"
        assert isinstance(resp.json(), list)
    sla = client.get("/api/v1/reports/dsr-sla", headers=ctx["headers"]).json()
    assert any(row["type"] == "EXPORT" and row["total"] == 1 for row in sla)
