import pytest

def test_full_incident_lifecycle(client, engineer_headers, admin_headers):
    # 1. Create incident (Open)
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "Payment Webhook Failures",
            "description": "Stripe webhook events failing HMAC validation.",
            "category": "Software",
            "severity": "High",
            "service": "Billing Gateway",
            "reporter": "support_agent"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]
    assert create_res.json()["status"] == "Open"
    assert create_res.json()["acknowledged_at"] is None

    # 2. Transition: Open -> In Progress
    trans_res1 = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "In Progress", "reason": "Engineer picked up ticket"},
        headers=engineer_headers
    )
    assert trans_res1.status_code == 200
    assert trans_res1.json()["status"] == "In Progress"
    assert trans_res1.json()["acknowledged_at"] is not None

    # 3. Transition: In Progress -> Pending
    trans_res2 = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={
            "status": "Pending",
            "pending_reason": "Awaiting webhook secret rotation from Stripe support"
        },
        headers=engineer_headers
    )
    assert trans_res2.status_code == 200
    assert trans_res2.json()["status"] == "Pending"
    assert trans_res2.json()["pending_reason"] == "Awaiting webhook secret rotation from Stripe support"

    # 4. Transition: Pending -> In Progress
    trans_res3 = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "In Progress", "reason": "Secret received, resuming remediation"},
        headers=engineer_headers
    )
    assert trans_res3.status_code == 200
    assert trans_res3.json()["status"] == "In Progress"

    # 5. Transition: In Progress -> Resolved
    trans_res4 = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={
            "status": "Resolved",
            "resolution_summary": "Rotated Stripe webhook signature secret in AWS Secrets Manager.",
            "root_cause": "Outdated signing secret used after Stripe API version upgrade.",
            "corrective_action": "Deployed updated secret to all payment worker containers."
        },
        headers=engineer_headers
    )
    assert trans_res4.status_code == 200
    res_data = trans_res4.json()
    assert res_data["status"] == "Resolved"
    assert res_data["resolved_at"] is not None
    assert res_data["time_to_resolve_hours"] is not None
    assert res_data["root_cause"] is not None

    # 6. Transition: Resolved -> Closed
    trans_res5 = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "Closed", "reason": "No recurrence after 24-hour observation window."},
        headers=engineer_headers
    )
    assert trans_res5.status_code == 200
    assert trans_res5.json()["status"] == "Closed"
    assert trans_res5.json()["closed_at"] is not None

def test_invalid_lifecycle_transition(client, engineer_headers):
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "DNS Latency",
            "description": "DNS queries slow",
            "category": "Network",
            "severity": "Low",
            "service": "Core DNS",
            "reporter": "engineer"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]

    # Open -> Closed directly is invalid
    res = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "Closed", "reason": "Invalid skip"},
        headers=engineer_headers
    )
    assert res.status_code == 400
    assert "Invalid status transition" in res.json()["message"]

def test_pending_requires_reason(client, engineer_headers):
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "API Gateway 504",
            "description": "Gateway timeouts",
            "category": "Software",
            "severity": "Medium",
            "service": "Gateway",
            "reporter": "engineer"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]

    # In Progress first
    client.post(f"/api/v1/incidents/{inc_id}/status", json={"status": "In Progress"}, headers=engineer_headers)

    # Missing pending_reason -> 422
    res = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "Pending"},
        headers=engineer_headers
    )
    assert res.status_code == 422

def test_resolved_requires_summary(client, engineer_headers):
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "VPN Outage",
            "description": "VPN connection drops",
            "category": "Network",
            "severity": "Medium",
            "service": "VPN",
            "reporter": "engineer"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]

    client.post(f"/api/v1/incidents/{inc_id}/status", json={"status": "In Progress"}, headers=engineer_headers)

    # Missing resolution_summary -> 422
    res = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "Resolved"},
        headers=engineer_headers
    )
    assert res.status_code == 422

def test_closed_incident_reopen_rbac(client, engineer_headers, admin_headers):
    # Setup closed incident
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "Storage Volume Degradation",
            "description": "RAID rebuild started",
            "category": "Hardware",
            "severity": "Medium",
            "service": "SAN Storage",
            "reporter": "dc_engineer"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]

    client.post(f"/api/v1/incidents/{inc_id}/status", json={"status": "In Progress"}, headers=engineer_headers)
    client.post(f"/api/v1/incidents/{inc_id}/status", json={"status": "Resolved", "resolution_summary": "Rebuilt RAID volume"}, headers=engineer_headers)
    client.post(f"/api/v1/incidents/{inc_id}/status", json={"status": "Closed", "reason": "Completed"}, headers=engineer_headers)

    # Attempting to edit a closed incident directly fails
    patch_res = client.patch(f"/api/v1/incidents/{inc_id}", json={"severity": "Low"}, headers=engineer_headers)
    assert patch_res.status_code == 400
    assert "Closed incidents cannot be modified" in patch_res.json()["message"]

    # Non-admin attempting to reopen Closed incident gets 403 Forbidden
    reopen_eng = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "In Progress", "reason": "Issue re-occurred"},
        headers=engineer_headers
    )
    assert reopen_eng.status_code == 403
    assert "Administrators" in reopen_eng.json()["message"]

    # Admin reopening Closed incident succeeds
    reopen_admin = client.post(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "In Progress", "reason": "Admin approved re-investigation"},
        headers=admin_headers
    )
    assert reopen_admin.status_code == 200
    assert reopen_admin.json()["status"] == "In Progress"
    assert reopen_admin.json()["closed_at"] is None
