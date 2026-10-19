import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import csv
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models.incident import Incident
from app.models.investigation_note import InvestigationNote
from app.models.activity import IncidentActivity
from app.schemas.common import SeverityEnum, PriorityEnum, IncidentStatusEnum
from app.utils.timezone import utc_now
from app.logging_config import logger

CURATED_INCIDENTS = [
    {
        "incident_number": "INC-2026-0001",
        "title": "PostgreSQL Primary Database Connection Pool Exhaustion",
        "description": "Production API gateway throwing 500 Internal Server Errors. Multiple microservices report 'FATAL: remaining connection slots are reserved for non-replication superuser connections'. Incoming checkout and payment flows blocked.",
        "category": "Database",
        "subcategory": "PostgreSQL",
        "severity": "Critical",
        "priority": "P1",
        "impact": "High",
        "urgency": "High",
        "status": "Closed",
        "service": "Checkout & Payments DB",
        "reporter": "pagerduty_alert_bot",
        "assignee": "sarah.chen@company.com",
        "assignment_group": "Database Reliability Team",
        "sla_resolution_target_hours": 4.0,
        "sla_response_target_hours": 0.25,
        "hours_ago_created": 48.0,
        "hours_to_ack": 0.1,
        "hours_to_resolve": 2.2,
        "hours_to_close": 24.0,
        "root_cause": "A newly deployed microservice (v2.14.0 of Inventory Service) failed to close database sessions in its bulk-inventory sync job exception handler. Under high concurrency, lingering idle-in-transaction connections rapidly consumed all 500 connections in PgBouncer pool.",
        "corrective_action": "1. Terminated orphaned idle connections via pg_terminate_backend().\n2. Rolled back Inventory Service deployment to v2.13.9.\n3. Increased PgBouncer pool ceiling temporarily from 500 to 750.",
        "preventive_action": "1. Added context manager connection leak detection unit tests to CI pipeline.\n2. Configured idle_in_transaction_session_timeout = 30000ms in PostgreSQL postgresql.conf.\n3. Added Prometheus alert for connection pool utilization exceeding 80%.",
        "resolution_summary": "Orphaned connections purged; faulty deployment rolled back. Database connection pool returned to nominal 12% capacity.",
        "notes": [
            ("Observation", "PagerDuty fired P1 alert: DB connection usage reached 100% (500/500).", "monitoring_bot", 47.9),
            ("Hypothesis", "Possible connection leak following the 02:00 UTC release of Inventory Service.", "sarah.chen@company.com", 47.5),
            ("Action", "Executed pg_terminate_backend on connections in 'idle in transaction' state for > 5 minutes.", "sarah.chen@company.com", 46.8),
            ("Evidence", "pg_stat_activity showed 380 connections originating from inventory-service-pod-7.", "sarah.chen@company.com", 46.5),
        ],
    },
    {
        "incident_number": "INC-2026-0002",
        "title": "Payment Gateway Ingress TLS Certificate Expired",
        "description": "Mobile and web clients receiving ERR_CERT_DATE_INVALID when submitting credit card authorization requests to api.payments.internal. Traffic drops 90%.",
        "category": "Security",
        "subcategory": "Certificates",
        "severity": "Critical",
        "priority": "P1",
        "impact": "High",
        "urgency": "High",
        "status": "Resolved",
        "service": "Payment Gateway",
        "reporter": "alex.kumar@company.com",
        "assignee": "marcus.vance@company.com",
        "assignment_group": "Platform SecOps",
        "sla_resolution_target_hours": 4.0,
        "sla_response_target_hours": 0.25,
        "hours_ago_created": 6.5,
        "hours_to_ack": 0.2,
        "hours_to_resolve": 5.8,  # Exceeded 4h -> Missed SLA
        "hours_to_close": None,
        "root_cause": "Cert-manager ACME webhook automation failed due to a missing IAM role policy following a cluster migration. Automatic renewal silent failure was unmonitored for this domain.",
        "corrective_action": "Manually generated and deployed wildcard wildcard.payments.internal certificate via DigiCert CA console; reloaded Nginx ingress controllers.",
        "preventive_action": "Integrated cert-manager Prometheus exporter with Slack notification 30, 14, and 7 days prior to certificate expiry. Added IAM role validation in Terraform CI.",
        "resolution_summary": "Valid TLS certificate provisioned and reloaded across all ingress nodes. Payment verification requests succeeding with 200 OK.",
        "notes": [
            ("Observation", "Clients unable to establish HTTPS handshake; SSL Labs reports certificate expired at 00:00 UTC.", "alex.kumar@company.com", 6.4),
            ("Action", "Initiated manual DigiCert issuance request with priority approval.", "marcus.vance@company.com", 5.0),
            ("Evidence", "Kubernetes cert-manager log: 'Failed to complete DNS-01 challenge: AccessDenied on Route53'.", "marcus.vance@company.com", 4.2),
        ],
    },
    {
        "incident_number": "INC-2026-0003",
        "title": "Kafka Consumer Lag Spike in Order Fulfillment Stream",
        "description": "Order processing pipeline consumer lag exceeded 45,000 messages on topic 'orders.v1'. Customer order confirmation emails delayed by > 45 minutes.",
        "category": "Infrastructure",
        "subcategory": "Message Queue",
        "severity": "High",
        "priority": "P2",
        "impact": "Medium",
        "urgency": "High",
        "status": "In Progress",
        "service": "Order Fulfillment Engine",
        "reporter": "kafka-monitor@company.com",
        "assignee": "elena.rostova@company.com",
        "assignment_group": "Backend Engineering",
        "sla_resolution_target_hours": 8.0,
        "sla_response_target_hours": 0.5,
        "hours_ago_created": 3.0,
        "hours_to_ack": 0.3,
        "hours_to_resolve": None,
        "hours_to_close": None,
        "root_cause": None,
        "corrective_action": None,
        "preventive_action": None,
        "resolution_summary": None,
        "notes": [
            ("Observation", "Consumer group order-processor-cg experiencing rebalance loop.", "kafka-monitor@company.com", 2.8),
            ("Hypothesis", "Heartbeat timeout triggered by long-running third-party address verification API call.", "elena.rostova@company.com", 2.0),
            ("Action", "Temporarily increased max.poll.interval.ms from 300000 to 600000 while profiling address validator.", "elena.rostova@company.com", 1.2),
        ],
    },
    {
        "incident_number": "INC-2026-0004",
        "title": "Kubernetes Ingress Nginx 502 Bad Gateway on User Portal",
        "description": "Users accessing user-portal.company.com encounter intermittent HTTP 502 Bad Gateway errors during traffic surges.",
        "category": "Software",
        "subcategory": "Frontend Gateway",
        "severity": "High",
        "priority": "P2",
        "impact": "Medium",
        "urgency": "High",
        "status": "Open",
        "service": "User Portal",
        "reporter": "support_lead@company.com",
        "assignee": None,
        "assignment_group": "Site Reliability Engineering",
        "sla_resolution_target_hours": 8.0,
        "sla_response_target_hours": 0.5,
        "hours_ago_created": 10.0,  # 10h ago > 8h target -> Overdue / Breached!
        "hours_to_ack": None,
        "hours_to_resolve": None,
        "hours_to_close": None,
        "root_cause": None,
        "corrective_action": None,
        "preventive_action": None,
        "resolution_summary": None,
        "notes": [
            ("Observation", "Spike in upstream connect timed out in ingress-nginx controller logs.", "support_lead@company.com", 9.8),
        ],
    },
    {
        "incident_number": "INC-2026-0005",
        "title": "CI/CD Runner Host Disk Space Exhaustion (/var/lib/docker)",
        "description": "GitLab CI builds failing with 'No space left on device'. Deployment pipeline stalled across 14 development teams.",
        "category": "Infrastructure",
        "subcategory": "DevOps",
        "severity": "Medium",
        "priority": "P3",
        "impact": "Medium",
        "urgency": "Low",
        "status": "Resolved",
        "service": "CI/CD Infrastructure",
        "reporter": "developer_advocate@company.com",
        "assignee": "jordan.lee@company.com",
        "assignment_group": "Platform Engineering",
        "sla_resolution_target_hours": 24.0,
        "sla_response_target_hours": 2.0,
        "hours_ago_created": 18.0,
        "hours_to_ack": 0.5,
        "hours_to_resolve": 3.5,  # 3.5h <= 24h -> Met SLA
        "hours_to_close": None,
        "root_cause": "Dangling Docker image layers and orphaned container build caches accumulated without automated daily system prune cron job.",
        "corrective_action": "Ran docker system prune -af --volumes releasing 420GB of disk space.",
        "preventive_action": "Configured nightly systemd timer for docker system prune with retention policy.",
        "resolution_summary": "Storage usage lowered to 24%. CI runner queue cleared.",
        "notes": [
            ("Action", "Executed docker prune across all 8 dedicated runner nodes.", "jordan.lee@company.com", 16.0),
        ],
    },
    {
        "incident_number": "INC-2026-0006",
        "title": "SSO Single Sign-On SAML Assertion Timeout",
        "description": "Internal employees unable to login to intranet dashboard via Okta SSO. Error: 'SAML response received outside of acceptable clock skew window'.",
        "category": "Security",
        "subcategory": "Identity & Access",
        "severity": "Medium",
        "priority": "P3",
        "impact": "Low",
        "urgency": "Medium",
        "status": "Pending",
        "pending_reason": "Awaiting vendor confirmation from Okta Support regarding NTP server drift.",
        "service": "Corporate Identity Provider",
        "reporter": "helpdesk_agent@company.com",
        "assignee": "marcus.vance@company.com",
        "assignment_group": "Corporate IT",
        "sla_resolution_target_hours": 24.0,
        "sla_response_target_hours": 2.0,
        "hours_ago_created": 4.0,
        "hours_to_ack": 0.4,
        "hours_to_resolve": None,
        "hours_to_close": None,
        "root_cause": None,
        "corrective_action": None,
        "preventive_action": None,
        "resolution_summary": None,
        "notes": [
            ("Observation", "NTP synchronization on internal auth cluster had drifted by +124 seconds.", "marcus.vance@company.com", 3.5),
            ("Action", "Synchronized Chrony daemon with time.google.com; opened vendor ticket with Okta.", "marcus.vance@company.com", 2.5),
        ],
    },
    {
        "incident_number": "INC-2026-0007",
        "title": "Weekly Batch Invoice Generation Cron Job Memory OOM",
        "description": "Nightly financial statement generation job crashed with SIGKILL (Exit code 137). Linux OOM killer terminated the worker process.",
        "category": "Software",
        "subcategory": "Billing Service",
        "severity": "Low",
        "priority": "P4",
        "impact": "Low",
        "urgency": "Low",
        "status": "Closed",
        "service": "Finance & Billing API",
        "reporter": "finance_batch_monitor",
        "assignee": "sarah.chen@company.com",
        "assignment_group": "Backend Engineering",
        "sla_resolution_target_hours": 72.0,
        "sla_response_target_hours": 4.0,
        "hours_ago_created": 90.0,
        "hours_to_ack": 1.2,
        "hours_to_resolve": 14.5,
        "hours_to_close": 48.0,
        "root_cause": "The billing batch loaded all enterprise tenant ledger records into a single in-memory Python list before chunking.",
        "corrective_action": "Converted the query to server-side cursor pagination processing 500 rows per batch.",
        "preventive_action": "Set cgroups hard memory limits with alert thresholds in Kubernetes worker spec.",
        "resolution_summary": "Memory consumption reduced from 8GB to 420MB. All invoices successfully generated.",
        "notes": [
            ("Observation", "Kernel dmesg: 'Out of memory: Killed process 31412 (python3) total-vm:8412800kB'.", "sarah.chen@company.com", 88.0),
        ],
    }
]

def seed_curated_data(db: Session) -> int:
    """Populates curated demo incidents with complete workflows and SLA statuses."""
    now = utc_now()
    created_count = 0

    for item in CURATED_INCIDENTS:
        existing = db.query(Incident).filter(Incident.incident_number == item["incident_number"]).first()
        if existing:
            continue

        created_at = now - timedelta(hours=item["hours_ago_created"])
        updated_at = created_at
        acknowledged_at = created_at + timedelta(hours=item["hours_to_ack"]) if item["hours_to_ack"] is not None else None
        resolved_at = created_at + timedelta(hours=item["hours_to_resolve"]) if item["hours_to_resolve"] is not None else None
        closed_at = created_at + timedelta(hours=item["hours_to_close"]) if item["hours_to_close"] is not None else None

        if closed_at:
            updated_at = closed_at
        elif resolved_at:
            updated_at = resolved_at
        elif acknowledged_at:
            updated_at = acknowledged_at

        inc = Incident(
            incident_number=item["incident_number"],
            title=item["title"],
            description=item["description"],
            category=item["category"],
            subcategory=item["subcategory"],
            severity=item["severity"],
            priority=item["priority"],
            impact=item["impact"],
            urgency=item["urgency"],
            status=item["status"],
            pending_reason=item.get("pending_reason"),
            service=item["service"],
            reporter=item["reporter"],
            assignee=item["assignee"],
            assignment_group=item["assignment_group"],
            root_cause=item["root_cause"],
            corrective_action=item["corrective_action"],
            preventive_action=item["preventive_action"],
            resolution_summary=item["resolution_summary"],
            sla_resolution_target_hours=item["sla_resolution_target_hours"],
            sla_response_target_hours=item["sla_response_target_hours"],
            created_at=created_at,
            updated_at=updated_at,
            acknowledged_at=acknowledged_at,
            resolved_at=resolved_at,
            closed_at=closed_at,
        )
        db.add(inc)
        db.flush()

        # Add initial activity
        db.add(IncidentActivity(
            incident_id=inc.id,
            action="CREATED",
            field_name="status",
            old_value=None,
            new_value="Open",
            performed_by=item["reporter"],
            notes=f"Incident logged by {item['reporter']}",
            timestamp=created_at
        ))

        if inc.assignee:
            db.add(IncidentActivity(
                incident_id=inc.id,
                action="ASSIGNED",
                field_name="assignee",
                old_value=None,
                new_value=inc.assignee,
                performed_by="system",
                notes=f"Assigned to {inc.assignee}",
                timestamp=created_at + timedelta(minutes=5)
            ))

        if inc.status in ("In Progress", "Pending", "Resolved", "Closed") and acknowledged_at:
            db.add(IncidentActivity(
                incident_id=inc.id,
                action="STATUS_CHANGED",
                field_name="status",
                old_value="Open",
                new_value="In Progress",
                performed_by=inc.assignee or "engineer",
                notes="Investigation started",
                timestamp=acknowledged_at
            ))

        if inc.status == "Pending":
            db.add(IncidentActivity(
                incident_id=inc.id,
                action="STATUS_CHANGED",
                field_name="status",
                old_value="In Progress",
                new_value="Pending",
                performed_by=inc.assignee or "engineer",
                notes=item.get("pending_reason", "Pending third-party"),
                timestamp=created_at + timedelta(hours=2)
            ))

        if inc.status in ("Resolved", "Closed") and resolved_at:
            db.add(IncidentActivity(
                incident_id=inc.id,
                action="RESOLVED",
                field_name="status",
                old_value="In Progress",
                new_value="Resolved",
                performed_by=inc.assignee or "engineer",
                notes=item["resolution_summary"] or "Resolved",
                timestamp=resolved_at
            ))

        if inc.status == "Closed" and closed_at:
            db.add(IncidentActivity(
                incident_id=inc.id,
                action="CLOSED",
                field_name="status",
                old_value="Resolved",
                new_value="Closed",
                performed_by="system",
                notes="Incident closed after customer validation",
                timestamp=closed_at
            ))

        # Add notes
        for note_type, note_content, note_author, hours_ago in item.get("notes", []):
            note_time = now - timedelta(hours=hours_ago)
            db.add(InvestigationNote(
                incident_id=inc.id,
                note_type=note_type,
                author=note_author,
                content=note_content,
                created_at=note_time
            ))
            db.add(IncidentActivity(
                incident_id=inc.id,
                action="NOTE_ADDED",
                field_name="notes",
                old_value=None,
                new_value=f"[{note_type}] {note_content[:50]}...",
                performed_by=note_author,
                notes=f"Note by {note_author}",
                timestamp=note_time
            ))

        created_count += 1

    db.commit()
    logger.info(f"Seeded {created_count} curated demo incidents.")
    return created_count

def import_from_csv(db: Session, csv_path: str, limit: int = 50) -> int:
    """Imports real incident traces from incident_event_log.csv."""
    if not os.path.exists(csv_path):
        logger.warning(f"CSV file not found at {csv_path}")
        return 0

    priority_map = {
        "1 - Critical": ("Critical", "P1", 4.0),
        "2 - High": ("High", "P2", 8.0),
        "3 - Moderate": ("Medium", "P3", 24.0),
        "4 - Low": ("Low", "P4", 72.0),
    }

    state_map = {
        "New": "Open",
        "Active": "In Progress",
        "Awaiting User Info": "Pending",
        "Awaiting Problem": "Pending",
        "Awaiting Evidence": "Pending",
        "Resolved": "Resolved",
        "Closed": "Closed",
    }

    imported_incidents = set()
    count = 0

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inc_num = row.get("number", "").strip()
            if not inc_num or inc_num in imported_incidents:
                continue

            existing = db.query(Incident).filter(Incident.incident_number == inc_num).first()
            if existing:
                continue

            raw_state = row.get("incident_state", "New")
            status = state_map.get(raw_state, "Open")
            
            raw_pri = row.get("priority", "3 - Moderate")
            sev, pri, sla_res = priority_map.get(raw_pri, ("Medium", "P3", 24.0))

            category = row.get("category", "Software").replace("Category ", "IT Service ")
            subcategory = row.get("subcategory", "")
            symptom = row.get("u_symptom", "System error")
            caller = row.get("caller_id", "Internal Reporter")
            assignee = row.get("assigned_to", "Unassigned")
            if assignee == "?":
                assignee = None
            assignment_group = row.get("assignment_group", "Tier 2 Support")

            # Parse opened_at e.g. "29/2/2016 01:16"
            try:
                opened_dt = datetime.strptime(row.get("opened_at", ""), "%d/%m/%Y %H:%M")
                opened_dt = opened_dt.replace(tzinfo=timezone.utc)
            except Exception:
                opened_dt = utc_now() - timedelta(days=1)

            resolved_dt = None
            if row.get("resolved_at") and row.get("resolved_at") != "?":
                try:
                    resolved_dt = datetime.strptime(row.get("resolved_at", ""), "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            closed_dt = None
            if row.get("closed_at") and row.get("closed_at") != "?":
                try:
                    closed_dt = datetime.strptime(row.get("closed_at", ""), "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            title = f"{category} Incident: {symptom}"
            desc = f"Reported by {caller}. Location: {row.get('location', 'Global')}. Contact Type: {row.get('contact_type', 'System')}. Impact: {row.get('impact', 'Medium')}, Urgency: {row.get('urgency', 'Medium')}."

            rca = None
            resolution = None
            if status in ("Resolved", "Closed"):
                rca = f"Root cause traced to configuration defect or intermittent resource bottleneck in {category}."
                resolution = f"Service restored via standard operational remediation. Closure code: {row.get('closed_code', 'Standard Resolution')}."

            incident = Incident(
                incident_number=inc_num,
                title=title,
                description=desc,
                category=category,
                subcategory=subcategory if subcategory != "?" else None,
                severity=sev,
                priority=pri,
                impact=row.get("impact", "2 - Medium").replace("2 - ", "").replace("1 - ", "").replace("3 - ", ""),
                urgency=row.get("urgency", "2 - Medium").replace("2 - ", "").replace("1 - ", "").replace("3 - ", ""),
                status=status,
                pending_reason="Awaiting customer details" if status == "Pending" else None,
                service=f"Enterprise {category}",
                reporter=caller,
                assignee=assignee,
                assignment_group=assignment_group if assignment_group != "?" else None,
                root_cause=rca,
                corrective_action="Applied service patch and recycled application pools." if status in ("Resolved", "Closed") else None,
                preventive_action="Updated monitoring threshold in APM." if status in ("Resolved", "Closed") else None,
                resolution_summary=resolution,
                sla_resolution_target_hours=sla_res,
                sla_response_target_hours=2.0,
                created_at=opened_dt,
                updated_at=closed_dt or resolved_dt or opened_dt,
                acknowledged_at=opened_dt + timedelta(minutes=15),
                resolved_at=resolved_dt,
                closed_at=closed_dt,
            )
            db.add(incident)
            db.flush()

            # Add activity
            db.add(IncidentActivity(
                incident_id=incident.id,
                action="CREATED",
                field_name="status",
                old_value=None,
                new_value="Open",
                performed_by=caller,
                notes="Imported from historic ITSM event log",
                timestamp=opened_dt
            ))

            imported_incidents.add(inc_num)
            count += 1
            if count >= limit:
                break

    db.commit()
    logger.info(f"Imported {count} real incidents from CSV dataset.")
    return count

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        print("Seeding curated demonstration incidents...")
        curated_n = seed_curated_data(db)
        print(f"Successfully seeded {curated_n} curated incidents.")

        csv_file = os.path.join("incident+management+process+enriched+event+log", "incident_event_log.csv")
        if os.path.exists(csv_file):
            print(f"Importing sample real records from {csv_file}...")
            csv_n = import_from_csv(db, csv_file, limit=25)
            print(f"Successfully imported {csv_n} incidents from CSV.")
    finally:
        db.close()
