from tests.conftest import auth_headers, make_org_user


def test_register_login_me_flow(client):
    ctx = make_org_user(client)
    assert ctx["me"]["role"] == "org_admin"
    resp = client.post("/api/v1/auth/login", json={
        "email": ctx["email"], "password": "Password123!", "organization_slug": ctx["slug"],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_login_wrong_password_rejected(client):
    ctx = make_org_user(client)
    resp = client.post("/api/v1/auth/login", json={
        "email": ctx["email"], "password": "WrongPass123!", "organization_slug": ctx["slug"],
    })
    assert resp.status_code == 401


def test_refresh_token_flow(client):
    ctx = make_org_user(client)
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": ctx["tokens"]["refresh_token"]})
    assert resp.status_code == 200, resp.text
    me = client.get("/api/v1/auth/me", headers=auth_headers(resp.json()["access_token"]))
    assert me.status_code == 200


def test_access_token_rejected_as_refresh(client):
    ctx = make_org_user(client)
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": ctx["tokens"]["access_token"]})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_duplicate_register_rejected(client):
    ctx = make_org_user(client)
    resp = client.post("/api/v1/auth/register", json={
        "organization_name": "X", "organization_slug": ctx["slug"],
        "email": ctx["email"], "password": "Password123!", "role": "org_admin",
    })
    assert resp.status_code == 409


def test_api_key_lifecycle(client):
    ctx = make_org_user(client)
    resp = client.post(f"/api/v1/organizations/{ctx['org_id']}/api-keys",
                       headers=ctx["headers"], json={"name": "server", "scopes": ["*"]})
    assert resp.status_code == 201, resp.text
    created = resp.json()
    raw = created["raw_key"]
    assert raw.startswith("cv_")
    # Raw key works for server-to-server calls.
    check = client.post("/api/v1/consents/check", headers={"X-API-Key": raw},
                        json={"external_ref": "nobody", "purpose_code": "marketing"})
    assert check.status_code == 200, check.text
    # Listing never returns the raw key.
    listing = client.get(f"/api/v1/organizations/{ctx['org_id']}/api-keys", headers=ctx["headers"])
    assert listing.status_code == 200
    assert "raw_key" not in listing.json()[0]
    assert "key_hash" not in listing.json()[0]
    # Revoke then key stops working.
    rev = client.delete(f"/api/v1/organizations/{ctx['org_id']}/api-keys/{created['id']}", headers=ctx["headers"])
    assert rev.status_code == 200
    denied = client.post("/api/v1/consents/check", headers={"X-API-Key": raw},
                         json={"external_ref": "nobody", "purpose_code": "marketing"})
    assert denied.status_code == 401


def test_rbac_data_subject_cannot_manage_purposes(client):
    ctx = make_org_user(client, role="data_subject")
    resp = client.post("/api/v1/purposes", headers=ctx["headers"],
                       json={"code": "x", "name": "X", "description": "", "legal_basis": "CONSENT"})
    assert resp.status_code == 403


def test_health_endpoint(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"
    assert "X-Request-ID" in resp.headers
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
