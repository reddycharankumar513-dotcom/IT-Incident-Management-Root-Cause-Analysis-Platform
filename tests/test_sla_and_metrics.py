from datetime import datetime, timezone, timedelta
from app.models.incident import Incident
from app.utils.timezone import utc_now

def test_sla_targets_and_overdue_detection(client, db_session, engineer_headers, viewer_headers):
    # 1. Create incident that is simulated as 10 hours old with a 4-hour SLA
    now = utc_now()
    created_old = now - timedelta(hours=10)

    old_incident = Incident(
        incident_number="INC-2026-9999",
        title="Unresolved Core Switch BGP Flap",
        description="BGP session flapping between DC-1 and DC-2.",
        category="Network",
        severity="Critical",
        priority="P1",
        status="In Progress",
        service="Data Center Interconnect",
        reporter="netops",
        assignee="sarah.chen@company.com",
        sla_resolution_target_hours=4.0,
        sla_response_target_hours=0.25,
        created_at=created_old,
        updated_at=created_old,
        acknowledged_at=created_old + timedelta(minutes=10)
    )
    db_session.add(old_incident)
    db_session.commit()

    # 2. Retrieve via API and verify overdue calculation
    res = client.get(f"/api/v1/incidents/{old_incident.id}", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_overdue"] is True
    assert data["sla_status"] == "Breached"
    assert data["age_hours"] >= 10.0

    # 3. Check /api/v1/incidents/overdue
    overdue_res = client.get("/api/v1/incidents/overdue", headers=viewer_headers)
    assert overdue_res.status_code == 200
    overdue_items = overdue_res.json()
    assert any(item["incident_number"] == "INC-2026-9999" for item in overdue_items)

def test_metrics_and_summary_reporting(client, db_session, engineer_headers, viewer_headers):
    now = utc_now()

    # Create resolved incident within SLA (2h <= 4h)
    inc_met = Incident(
        incident_number="INC-2026-1001",
        title="Resolved within SLA",
        description="Resolved fast",
        category="Software",
        severity="Critical",
        priority="P1",
        status="Resolved",
        service="Web App",
        reporter="agent1",
        assignee="eng1",
        sla_resolution_target_hours=4.0,
        sla_response_target_hours=0.25,
        created_at=now - timedelta(hours=5),
        updated_at=now - timedelta(hours=3),
        acknowledged_at=now - timedelta(hours=4.9),
        resolved_at=now - timedelta(hours=3),
        resolution_summary="Fixed issue"
    )

    # Create resolved incident that missed SLA (10h > 8h)
    inc_missed = Incident(
        incident_number="INC-2026-1002",
        title="Resolved late",
        description="Took too long",
        category="Database",
        severity="High",
        priority="P2",
        status="Resolved",
        service="Core DB",
        reporter="agent2",
        assignee="eng2",
        sla_resolution_target_hours=8.0,
        sla_response_target_hours=0.5,
        created_at=now - timedelta(hours=15),
        updated_at=now - timedelta(hours=5),
        acknowledged_at=now - timedelta(hours=14.5),
        resolved_at=now - timedelta(hours=5),
        resolution_summary="Resolved after 10 hours"
    )

    db_session.add_all([inc_met, inc_missed])
    db_session.commit()

    # Test /api/v1/reports/metrics
    metrics_res = client.get("/api/v1/reports/metrics", headers=viewer_headers)
    assert metrics_res.status_code == 200
    m = metrics_res.json()
    assert m["total_incidents"] == 2
    assert m["resolved_or_closed"] == 2
    # 1 of 2 met SLA -> 50%
    assert m["overall_compliance_rate_pct"] == 50.0
    assert m["overall_mttr_hours"] > 0.0

    # Test /api/v1/reports/summary
    summary_res = client.get("/api/v1/reports/summary", headers=viewer_headers)
    assert summary_res.status_code == 200
    s = summary_res.json()
    assert "operational_health_status" in s
    assert "summary_notes" in s

    # Test /api/v1/reports/sla-compliance
    sla_res = client.get("/api/v1/reports/sla-compliance", headers=viewer_headers)
    assert sla_res.status_code == 200
    sc = sla_res.json()
    assert sc["total_completed"] == 2
    assert sc["met_sla_count"] == 1
    assert sc["missed_sla_count"] == 1
    assert sc["compliance_rate_pct"] == 50.0
