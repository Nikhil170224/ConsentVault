import uuid

import pytest
from sqlalchemy import text

from tests.conftest import grant, make_org_user, make_purpose


def test_grant_and_check_flow(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    resp = grant(client, ctx["headers"], "user-1")
    assert resp.status_code == 201, resp.text
    check = client.post("/api/v1/consents/check", headers=ctx["headers"],
                        json={"external_ref": "user-1", "purpose_code": "marketing"})
    assert check.json()["has_consent"] is True


def test_grant_is_idempotent(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    first = grant(client, ctx["headers"], "user-1").json()[0]
    second = grant(client, ctx["headers"], "user-1").json()[0]
    assert first["id"] == second["id"]
    events = client.get("/api/v1/audit/events", headers=ctx["headers"]).json()
    assert len([e for e in events if e["event_type"] == "consent.granted"]) == 1


def test_withdraw_flow(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    consent = grant(client, ctx["headers"], "user-1").json()[0]
    resp = client.post(f"/api/v1/consents/{consent['id']}/withdraw", headers=ctx["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "WITHDRAWN"
    check = client.post("/api/v1/consents/check", headers=ctx["headers"],
                        json={"external_ref": "user-1", "purpose_code": "marketing"})
    assert check.json()["has_consent"] is False
    # Double withdraw -> 409.
    again = client.post(f"/api/v1/consents/{consent['id']}/withdraw", headers=ctx["headers"])
    assert again.status_code == 409


def test_required_purpose_cannot_be_withdrawn(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"], code="core", is_required=True)
    consent = grant(client, ctx["headers"], "user-1", purpose_code="core").json()[0]
    resp = client.post(f"/api/v1/consents/{consent['id']}/withdraw", headers=ctx["headers"])
    assert resp.status_code == 409
    assert "required" in resp.json()["detail"]


def test_subject_consents_and_history(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    consent = grant(client, ctx["headers"], "user-1").json()[0]
    subject_id = consent["data_subject_id"]
    current = client.get(f"/api/v1/data-subjects/{subject_id}/consents", headers=ctx["headers"])
    assert current.status_code == 200
    assert current.json()[0]["purpose_code"] == "marketing"
    client.post(f"/api/v1/consents/{consent['id']}/withdraw", headers=ctx["headers"])
    history = client.get(f"/api/v1/data-subjects/{subject_id}/consents/history", headers=ctx["headers"])
    types = [e["event_type"] for e in history.json()]
    assert types == ["consent.granted", "consent.withdrawn"]


def test_verify_chain_intact(client):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    grant(client, ctx["headers"], "user-1")
    grant(client, ctx["headers"], "user-2")
    resp = client.get("/api/v1/audit/verify-chain", headers=ctx["headers"])
    assert resp.json()["intact"] is True
    assert resp.json()["events_checked"] == 2


def test_trigger_blocks_update_and_delete(client, db_session):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    grant(client, ctx["headers"], "user-1")
    with pytest.raises(Exception, match="append-only"):
        db_session.execute(text("UPDATE consent_events SET event_type='tampered'"))
        db_session.commit()
    db_session.rollback()
    with pytest.raises(Exception, match="append-only"):
        db_session.execute(text("DELETE FROM consent_events"))
        db_session.commit()
    db_session.rollback()


def test_tamper_detection_breaks_chain(client, db_session):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    grant(client, ctx["headers"], "user-1")
    grant(client, ctx["headers"], "user-2")
    assert client.get("/api/v1/audit/verify-chain", headers=ctx["headers"]).json()["intact"] is True
    # Test-only bypass: disable triggers, tamper with a row, re-enable.
    db_session.execute(text("ALTER TABLE consent_events DISABLE TRIGGER ALL"))
    db_session.execute(text("UPDATE consent_events SET new_status='WITHDRAWN' WHERE event_type='consent.granted'"))
    db_session.execute(text("ALTER TABLE consent_events ENABLE TRIGGER ALL"))
    db_session.commit()
    result = client.get("/api/v1/audit/verify-chain", headers=ctx["headers"]).json()
    assert result["intact"] is False
    assert result["broken_event_id"] is not None


def test_expiry_sweep(client, db_session):
    ctx = make_org_user(client)
    make_purpose(client, ctx["headers"])
    resp = client.post("/api/v1/consents", headers=ctx["headers"], json={
        "external_ref": "user-1", "email": "user-1@example.com",
        "purposes": [{"purpose_code": "marketing", "expires_at": "2020-01-01T00:00:00Z"}],
        "source": "web",
    })
    assert resp.status_code == 201, resp.text
    swept = client.post("/api/v1/admin/sweep-expired", headers=ctx["headers"])
    assert swept.json()["expired_count"] == 1
    check = client.post("/api/v1/consents/check", headers=ctx["headers"],
                        json={"external_ref": "user-1", "purpose_code": "marketing"})
    assert check.json()["has_consent"] is False


def test_purpose_versioning(client):
    ctx = make_org_user(client)
    purpose = make_purpose(client, ctx["headers"])
    updated = client.patch(f"/api/v1/purposes/{purpose['id']}", headers=ctx["headers"],
                           json={"description": "New description"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["id"] != purpose["id"]
    # Non-versioned field updates in place.
    renamed = client.patch(f"/api/v1/purposes/{updated.json()['id']}", headers=ctx["headers"],
                           json={"name": "Renamed"})
    assert renamed.json()["id"] == updated.json()["id"]
    assert renamed.json()["name"] == "Renamed"


def test_grant_unknown_purpose_404(client):
    ctx = make_org_user(client)
    resp = grant(client, ctx["headers"], "user-1", purpose_code="nonexistent")
    assert resp.status_code == 404
    assert uuid.UUID(int=0) is not None
