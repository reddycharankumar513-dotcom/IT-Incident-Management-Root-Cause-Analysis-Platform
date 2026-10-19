import pytest

def test_root_and_health(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "platform" in res.json()
    assert res.json()["version"] == "2.0.0"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

def test_create_incident_success(client, engineer_headers):
    payload = {
        "title": "PostgreSQL Connection Pool Exhaustion",
        "description": "PgBouncer reached connection threshold of 500 connections. Checkout service failing.",
        "category": "Database",
        "severity": "Critical",
        "service": "Payments DB",
        "reporter": "monitoring_bot",
        "assignee": "sarah.chen@company.com"
    }
    response = client.post("/api/v1/incidents", json=payload, headers=engineer_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["incident_number"].startswith("INC-")
    assert data["title"] == payload["title"]
    assert data["severity"] == "Critical"
    assert data["priority"] == "P1"  # Derived automatically
    assert data["status"] == "Open"
    assert data["sla_resolution_target_hours"] == 4.0  # Critical default SLA
    assert data["is_overdue"] is False
    assert data["sla_status"] == "Within SLA"

def test_create_incident_validation_error(client, engineer_headers):
    # Missing title & invalid severity
    payload = {
        "title": "A",  # too short (< 3)
        "description": "Short",
        "severity": "UltraCritical",  # invalid
        "service": "DB",
        "reporter": "tester"
    }
    response = client.post("/api/v1/incidents", json=payload, headers=engineer_headers)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] is True

def test_get_incident_by_id_and_number(client, engineer_headers, viewer_headers):
    payload = {
        "title": "Redis Memory Fragmentation",
        "description": "Memory fragmentation ratio reached 2.4 on session cache cluster.",
        "category": "Infrastructure",
        "severity": "High",
        "service": "Session Cache",
        "reporter": "devops_lead"
    }
    create_res = client.post("/api/v1/incidents", json=payload, headers=engineer_headers)
    assert create_res.status_code == 201
    created = create_res.json()
    inc_id = created["id"]
    inc_num = created["incident_number"]

    # Retrieve by numeric ID
    res_id = client.get(f"/api/v1/incidents/{inc_id}", headers=viewer_headers)
    assert res_id.status_code == 200
    assert res_id.json()["incident_number"] == inc_num
    assert "notes" in res_id.json()
    assert "activities" in res_id.json()

    # Retrieve by business incident number
    res_num = client.get(f"/api/v1/incidents/{inc_num}", headers=viewer_headers)
    assert res_num.status_code == 200
    assert res_num.json()["id"] == inc_id

def test_get_incident_not_found(client, viewer_headers):
    response = client.get("/api/v1/incidents/99999", headers=viewer_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["message"].lower()

def test_update_incident_metadata(client, engineer_headers):
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "Network Packet Loss in US-East-1",
            "description": "Intermittent 15% packet loss observed on border routers.",
            "category": "Network",
            "severity": "Medium",
            "service": "Backbone Network",
            "reporter": "netops"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]

    # Update metadata
    update_res = client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"assignee": "marcus.vance@company.com", "severity": "High"},
        headers=engineer_headers
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["assignee"] == "marcus.vance@company.com"
    assert updated["severity"] == "High"

    # Verify activity was recorded
    detail_res = client.get(f"/api/v1/incidents/{inc_id}", headers=engineer_headers)
    activities = detail_res.json()["activities"]
    assert any(a["action"] == "UPDATED" and a["field_name"] == "assignee" for a in activities)

def test_update_incident_empty_payload(client, engineer_headers):
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "Kafka Consumer Lag",
            "description": "Consumer lag exceeds 10000 msgs",
            "category": "Infrastructure",
            "severity": "Medium",
            "service": "Streaming",
            "reporter": "dev"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]

    update_res = client.patch(f"/api/v1/incidents/{inc_id}", json={}, headers=engineer_headers)
    assert update_res.status_code == 400

def test_search_and_filters(client, engineer_headers, viewer_headers):
    # Create two distinct incidents
    client.post(
        "/api/v1/incidents",
        json={
            "title": "Elasticsearch cluster yellow health",
            "description": "Unassigned replica shards on log analytics index.",
            "category": "Database",
            "severity": "Low",
            "service": "LogSearch",
            "reporter": "sysadmin",
            "assignee": "sarah.chen@company.com"
        },
        headers=engineer_headers
    )
    client.post(
        "/api/v1/incidents",
        json={
            "title": "Auth API 500 Spike",
            "description": "JWT token signature verification failures during deploy.",
            "category": "Security",
            "severity": "Critical",
            "service": "Authentication Service",
            "reporter": "sre_bot",
            "assignee": "marcus.vance@company.com"
        },
        headers=engineer_headers
    )

    # Search keyword
    search_res = client.get("/api/v1/incidents?search=Elasticsearch", headers=viewer_headers)
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1
    assert "Elasticsearch" in search_res.json()["items"][0]["title"]

    # Filter by severity
    crit_res = client.get("/api/v1/incidents?severity=Critical", headers=viewer_headers)
    assert crit_res.status_code == 200
    assert crit_res.json()["total"] == 1
    assert crit_res.json()["items"][0]["severity"] == "Critical"

    # Filter by category
    sec_res = client.get("/api/v1/incidents?category=Security", headers=viewer_headers)
    assert sec_res.status_code == 200
    assert sec_res.json()["total"] == 1
