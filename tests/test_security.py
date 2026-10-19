import pytest
from app.logging_config import SensitiveDataFilter

def test_unauthenticated_request_fails(client):
    # Calling protected endpoint without any auth
    res = client.post(
        "/api/v1/incidents",
        json={"title": "Test", "description": "Test", "service": "Test", "reporter": "Test"}
    )
    assert res.status_code == 401
    assert "WWW-Authenticate" in res.headers

def test_viewer_rbac_restrictions(client, viewer_headers, engineer_headers):
    # Engineer creates incident
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "Auth RBAC Test Incident",
            "description": "Checking authorization barriers.",
            "category": "Security",
            "severity": "Low",
            "service": "IAM",
            "reporter": "engineer_user"
        },
        headers=engineer_headers
    )
    assert create_res.status_code == 201
    inc_id = create_res.json()["id"]

    # Viewer CAN read
    get_res = client.get(f"/api/v1/incidents/{inc_id}", headers=viewer_headers)
    assert get_res.status_code == 200

    # Viewer CANNOT create
    create_viewer = client.post(
        "/api/v1/incidents",
        json={"title": "Unauthorized", "description": "Should fail", "service": "IAM", "reporter": "viewer"},
        headers=viewer_headers
    )
    assert create_viewer.status_code == 403
    assert "Operation not permitted" in create_viewer.json()["message"]

    # Viewer CANNOT update
    patch_viewer = client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"severity": "High"},
        headers=viewer_headers
    )
    assert patch_viewer.status_code == 403

def test_basic_authentication_success(client, basic_auth_engineer, basic_auth_admin):
    # Basic auth engineer can create
    res = client.post(
        "/api/v1/incidents",
        json={
            "title": "Basic Auth Incident",
            "description": "Created using HTTP Basic credentials",
            "category": "Software",
            "severity": "Low",
            "service": "Auth API",
            "reporter": "basic_engineer"
        },
        headers=basic_auth_engineer
    )
    assert res.status_code == 201
    assert res.json()["title"] == "Basic Auth Incident"

    # Basic auth admin can call seed endpoint
    seed_res = client.post("/api/v1/seed/sample-data", headers=basic_auth_admin)
    assert seed_res.status_code == 200

def test_sensitive_data_logging_mask():
    f = SensitiveDataFilter()
    raw_log = "User passed password='supersecretpassword123' and bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and api_key='sk_live_9999999999'"
    masked = f.mask_sensitive(raw_log)
    assert "supersecretpassword123" not in masked
    assert "sk_live_9999999999" not in masked
    assert "***REDACTED***" in masked
