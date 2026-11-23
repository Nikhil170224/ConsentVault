"""Tenant A must never read or modify tenant B's data, on every endpoint."""
from tests.conftest import grant, make_org_user, make_purpose


def _setup_two_tenants(client):
    a = make_org_user(client)
    b = make_org_user(client)
    make_purpose(client, a["headers"])
    purpose_b = make_purpose(client, b["headers"])
    consent_b = grant(client, b["headers"], "b-user").json()[0]
    dsr_b = client.post("/api/v1/dsr", headers=b["headers"],
                        json={"external_ref": "b-user", "type": "EXPORT"}).json()
    webhook_b = client.post("/api/v1/webhooks", headers=b["headers"], json={
        "url": "https://hooks.example.com/b", "secret": "whsec_bsecret1", "events": [],
    }).json()
    return a, b, purpose_b, consent_b, dsr_b, webhook_b


def test_purposes_isolated(client):
    a, b, purpose_b, *_ = _setup_two_tenants(client)
    assert client.get(f"/api/v1/purposes/{purpose_b['id']}", headers=a["headers"]).status_code == 404
    assert client.patch(f"/api/v1/purposes/{purpose_b['id']}", headers=a["headers"],
                        json={"name": "Hacked"}).status_code == 404
    assert client.delete(f"/api/v1/purposes/{purpose_b['id']}", headers=a["headers"]).status_code == 404
    codes_a = [p["id"] for p in client.get("/api/v1/purposes", headers=a["headers"]).json()]
    assert purpose_b["id"] not in codes_a


def test_consents_isolated(client):
    a, b, purpose_b, consent_b, *_ = _setup_two_tenants(client)
    assert client.post(f"/api/v1/consents/{consent_b['id']}/withdraw",
                       headers=a["headers"]).status_code == 404
    subject_b = consent_b["data_subject_id"]
    assert client.get(f"/api/v1/data-subjects/{subject_b}/consents",
                      headers=a["headers"]).status_code == 404
    assert client.get(f"/api/v1/data-subjects/{subject_b}/consents/history",
                      headers=a["headers"]).status_code == 404
    check = client.post("/api/v1/consents/check", headers=a["headers"],
                        json={"external_ref": "b-user", "purpose_code": "marketing"})
    assert check.json()["has_consent"] is False


def test_dsr_isolated(client):
    a, b, purpose_b, consent_b, dsr_b, _ = _setup_two_tenants(client)
    assert client.get(f"/api/v1/dsr/{dsr_b['id']}", headers=a["headers"]).status_code == 404
    assert client.patch(f"/api/v1/dsr/{dsr_b['id']}/status", headers=a["headers"],
                        json={"status": "VERIFYING"}).status_code == 404
    assert client.get(f"/api/v1/dsr/{dsr_b['id']}/download", headers=a["headers"]).status_code == 404
    ids_a = [d["id"] for d in client.get("/api/v1/dsr", headers=a["headers"]).json()]
    assert dsr_b["id"] not in ids_a


def test_webhooks_and_audit_isolated(client):
    a, b, purpose_b, consent_b, dsr_b, webhook_b = _setup_two_tenants(client)
    assert client.patch(f"/api/v1/webhooks/{webhook_b['id']}", headers=a["headers"],
                        json={"url": "https://evil.example.com"}).status_code == 404
    assert client.delete(f"/api/v1/webhooks/{webhook_b['id']}", headers=a["headers"]).status_code == 404
    events_a = client.get("/api/v1/audit/events", headers=a["headers"]).json()
    assert events_a == []
    verify_a = client.get("/api/v1/audit/verify-chain", headers=a["headers"]).json()
    assert verify_a["events_checked"] == 0


def test_org_and_api_keys_isolated(client):
    a, b, *_ = _setup_two_tenants(client)
    assert client.get(f"/api/v1/organizations/{b['org_id']}", headers=a["headers"]).status_code == 404
    assert client.post(f"/api/v1/organizations/{b['org_id']}/api-keys", headers=a["headers"],
                       json={"name": "evil", "scopes": ["*"]}).status_code == 404
    assert client.get(f"/api/v1/organizations/{b['org_id']}/api-keys",
                      headers=a["headers"]).status_code == 404


def test_reports_isolated(client):
    a, b, *_ = _setup_two_tenants(client)
    rates_a = client.get("/api/v1/reports/consent-rates", headers=a["headers"]).json()
    assert rates_a == []
    sla_a = client.get("/api/v1/reports/dsr-sla", headers=a["headers"]).json()
    assert sla_a == []
