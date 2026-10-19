import pytest

def test_investigation_notes_workflow(client, engineer_headers, viewer_headers):
    # Create incident
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "Database Read Replicas Out of Sync",
            "description": "Replication lag jumped to 45 minutes on read replicas.",
            "category": "Database",
            "severity": "High",
            "service": "Reporting Database",
            "reporter": "bi_analyst"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]

    # 1. Add Observation Note
    n1 = client.post(
        f"/api/v1/incidents/{inc_id}/notes",
        json={
            "note_type": "Observation",
            "content": "Replication stream lagging by 3.2GB on replica-db-02.",
            "author": "sarah.chen@company.com"
        },
        headers=engineer_headers
    )
    assert n1.status_code == 201
    assert n1.json()["note_type"] == "Observation"

    # 2. Add Hypothesis Note
    n2 = client.post(
        f"/api/v1/incidents/{inc_id}/notes",
        json={
            "note_type": "Hypothesis",
            "content": "A large unindexed batch UPDATE job on the primary WAL is overwhelming IOPS.",
            "author": "sarah.chen@company.com"
        },
        headers=engineer_headers
    )
    assert n2.status_code == 201

    # 3. Add Action Note
    n3 = client.post(
        f"/api/v1/incidents/{inc_id}/notes",
        json={
            "note_type": "Action",
            "content": "Throttled bulk update transaction rate to 500 rows per second.",
            "author": "sarah.chen@company.com"
        },
        headers=engineer_headers
    )
    assert n3.status_code == 201

    # 4. List notes
    list_notes_res = client.get(f"/api/v1/incidents/{inc_id}/notes", headers=viewer_headers)
    assert list_notes_res.status_code == 200
    notes = list_notes_res.json()
    assert len(notes) == 3
    assert notes[0]["note_type"] == "Observation"
    assert notes[1]["note_type"] == "Hypothesis"
    assert notes[2]["note_type"] == "Action"

def test_rca_documentation_and_audit_trail(client, engineer_headers, viewer_headers):
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "Memory Leak in User Profile API",
            "description": "Golang heap profile shows continuous RSS memory growth until OOM crash.",
            "category": "Software",
            "severity": "Medium",
            "service": "User Profile Service",
            "reporter": "perf_engineer"
        },
        headers=engineer_headers
    )
    inc_id = create_res.json()["id"]

    # Update RCA
    rca_payload = {
        "root_cause": "Goroutine leak caused by unbuffered channel write in HTTP timeout handler.",
        "corrective_action": "Patched channel to buffered capacity of 1 and added context cancellation listener.",
        "preventive_action": "Added goleak testing library to profile service unit test suite.",
        "resolution_summary": "Service memory stable at 120MB RSS under peak load."
    }
    rca_res = client.put(f"/api/v1/incidents/{inc_id}/rca", json=rca_payload, headers=engineer_headers)
    assert rca_res.status_code == 200
    rca_data = rca_res.json()
    assert rca_data["root_cause"] == rca_payload["root_cause"]
    assert rca_data["corrective_action"] == rca_payload["corrective_action"]

    # Check incident detail reflects RCA
    detail_res = client.get(f"/api/v1/incidents/{inc_id}", headers=viewer_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["root_cause"] == rca_payload["root_cause"]

    # Check activity history includes CREATED and RCA_UPDATED
    act_res = client.get(f"/api/v1/incidents/{inc_id}/activities", headers=viewer_headers)
    assert act_res.status_code == 200
    actions = [a["action"] for a in act_res.json()]
    assert "CREATED" in actions
    assert "RCA_UPDATED" in actions
