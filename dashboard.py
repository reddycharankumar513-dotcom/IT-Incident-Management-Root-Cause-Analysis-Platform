import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone

from app.database import SessionLocal, init_db
from app.models.incident import Incident
from app.services.incident_service import IncidentService
from app.services.metrics_service import MetricsService
from app.services.rca_service import RcaService
from app.schemas.incident import IncidentCreate, StatusTransitionRequest
from app.schemas.note import InvestigationNoteCreate
from app.schemas.rca import RcaUpdateRequest
from app.schemas.common import SeverityEnum, PriorityEnum, IncidentStatusEnum, NoteTypeEnum, UserRole
from app.utils.timezone import utc_now, format_iso
from scripts.seed_data import seed_curated_data

# Ensure tables exist
init_db()

# Page setup
st.set_page_config(
    page_title="IT Incident Management & RCA Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #0d6efd;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .badge-critical {
        background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;
    }
    .badge-high {
        background-color: #fd7e14; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;
    }
    .badge-medium {
        background-color: #ffc107; color: black; padding: 3px 8px; border-radius: 4px; font-weight: bold;
    }
    .badge-low {
        background-color: #20c997; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;
    }
    .badge-overdue {
        background-color: #842029; color: #f8d7da; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; font-weight: bold;
    }
    .status-open { color: #0d6efd; font-weight: bold; }
    .status-inprogress { color: #6f42c1; font-weight: bold; }
    .status-pending { color: #fd7e14; font-weight: bold; }
    .status-resolved { color: #198754; font-weight: bold; }
    .status-closed { color: #6c757d; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Helper function to get database session
def get_db_session():
    return SessionLocal()

# Load data helper
def load_all_incidents():
    db = get_db_session()
    try:
        incidents, _ = IncidentService.list_incidents(db, page_size=1000)
        return incidents
    finally:
        db.close()

def load_metrics():
    db = get_db_session()
    try:
        return MetricsService.get_metrics_summary(db)
    finally:
        db.close()

def load_executive_report():
    db = get_db_session()
    try:
        return MetricsService.get_executive_summary_report(db)
    finally:
        db.close()

# Sidebar Navigation & Controls
st.sidebar.title("🛡️ IT Incident & RCA")
st.sidebar.caption("ITIL Incident Lifecycle, SLA & Root Cause Platform")

# Health Status & Quick Action
db = get_db_session()
total_in_db = db.query(Incident).count()
db.close()

if total_in_db == 0:
    st.sidebar.warning("Database is empty!")
    if st.sidebar.button("📥 Load Sample Incidents"):
        db = get_db_session()
        seed_curated_data(db)
        db.close()
        st.sidebar.success("Sample data loaded!")
        st.rerun()

nav_section = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard & Metrics", "📋 Incident Explorer & RCA", "➕ Log New Incident", "⚙️ Database Admin"]
)

# -------------------------------------------------------------
# TAB 1: DASHBOARD & METRICS
# -------------------------------------------------------------
if nav_section == "📊 Dashboard & Metrics":
    st.title("IT Operations & Incident Analytics")
    st.caption(f"Live System Time: {format_iso(utc_now())}")

    report = load_executive_report()
    m = report.metrics

    # Health Alert Banner
    health_status = report.operational_health_status
    if health_status == "Critical Action Required":
        st.error(f"🚨 **Operational Status: {health_status}** — {report.summary_notes}")
    elif health_status == "Warning":
        st.warning(f"⚠️ **Operational Status: {health_status}** — {report.summary_notes}")
    else:
        st.success(f"✅ **Operational Status: {health_status}** — {report.summary_notes}")

    # Top KPI Metrics Row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Incidents", m.total_incidents)
    with col2:
        st.metric("Active Workload", m.active_incidents, delta=f"{m.resolved_or_closed} Resolved", delta_color="normal")
    with col3:
        st.metric("SLA Breached / Overdue", m.overdue_count, delta=f"-{m.overdue_count}" if m.overdue_count > 0 else "0", delta_color="inverse")
    with col4:
        st.metric("SLA Compliance Rate", f"{m.overall_compliance_rate_pct}%", delta="Target: >= 90%")
    with col5:
        st.metric("Mean Time to Resolve", f"{m.overall_mttr_hours} hrs", delta=f"MTTA: {m.overall_mtta_hours} hrs")

    st.markdown("---")

    # Visual Analytics Charts Row
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Incidents by Severity")
        if m.by_severity:
            sev_df = pd.DataFrame([b.model_dump() for b in m.by_severity])
            color_map = {
                "Critical": "#dc3545",
                "High": "#fd7e14",
                "Medium": "#ffc107",
                "Low": "#20c997"
            }
            fig_sev = px.pie(
                sev_df,
                names="name",
                values="count",
                hole=0.45,
                color="name",
                color_discrete_map=color_map,
                title="Severity Distribution"
            )
            fig_sev.update_traces(textposition='inside', textinfo='percent+label')
            fig_sev.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_sev, use_container_width=True)
        else:
            st.info("No data available.")

    with chart_col2:
        st.subheader("Lifecycle Status Distribution")
        if m.by_status:
            stat_df = pd.DataFrame([b.model_dump() for b in m.by_status])
            stat_color_map = {
                "Open": "#0d6efd",
                "In Progress": "#6f42c1",
                "Pending": "#fd7e14",
                "Resolved": "#198754",
                "Closed": "#6c757d"
            }
            fig_stat = px.bar(
                stat_df,
                x="name",
                y="count",
                color="name",
                color_discrete_map=stat_color_map,
                text="count",
                labels={"name": "Status", "count": "Count"},
                title="Active vs Completed Status"
            )
            fig_stat.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=300, showlegend=False)
            st.plotly_chart(fig_stat, use_container_width=True)
        else:
            st.info("No data available.")

    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        st.subheader("Incidents by IT Category")
        if m.by_category:
            cat_df = pd.DataFrame([b.model_dump() for b in m.by_category])
            fig_cat = px.bar(
                cat_df,
                y="name",
                x="count",
                orientation='h',
                labels={"name": "Category", "count": "Incidents"},
                color="count",
                color_continuous_scale="Viridis",
                title="Service Domain Impact"
            )
            fig_cat.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No data available.")

    with chart_col4:
        st.subheader("Mean Time to Resolve (MTTR) by Severity")
        if m.mttr_by_severity:
            mttr_df = pd.DataFrame([
                {"Severity": k, "MTTR (Hours)": v}
                for k, v in m.mttr_by_severity.items()
            ])
            fig_mttr = px.bar(
                mttr_df,
                x="Severity",
                y="MTTR (Hours)",
                color="Severity",
                color_discrete_map={
                    "Critical": "#dc3545", "High": "#fd7e14", "Medium": "#ffc107", "Low": "#20c997"
                },
                text="MTTR (Hours)",
                title="Resolution Time Analysis"
            )
            fig_mttr.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=300, showlegend=False)
            st.plotly_chart(fig_mttr, use_container_width=True)
        else:
            st.info("No resolved incidents available for MTTR calculation.")

    # High Priority Alerts
    if report.critical_unresolved or report.overdue_active:
        st.markdown("---")
        st.subheader("⚠️ Urgent Action Required")
        alert_cols = st.columns(2)
        with alert_cols[0]:
            st.write(f"**Open Critical Incidents ({len(report.critical_unresolved)})**")
            for inc in report.critical_unresolved:
                st.error(f"**{inc.incident_number}**: {inc.title} (Service: `{inc.service}` | Assignee: `{inc.assignee or 'UNASSIGNED'}` | Age: {inc.age_human_readable})")
        with alert_cols[1]:
            st.write(f"**Overdue / Breached Active Incidents ({len(report.overdue_active)})**")
            for inc in report.overdue_active:
                st.warning(f"**{inc.incident_number}**: {inc.title} (Status: `{inc.status}` | Target: `{inc.sla_resolution_target_hours}h` | Age: {inc.age_human_readable})")

# -------------------------------------------------------------
# TAB 2: INCIDENT EXPLORER & RCA DEEP DIVE
# -------------------------------------------------------------
elif nav_section == "📋 Incident Explorer & RCA":
    st.title("Incident Management & RCA Workspace")

    # Filters
    st.sidebar.subheader("Filter Incidents")
    search_q = st.sidebar.text_input("🔍 Search keyword", placeholder="title, service, RCA...")
    status_filter = st.sidebar.selectbox("Status", ["All", "Open", "In Progress", "Pending", "Resolved", "Closed"])
    severity_filter = st.sidebar.selectbox("Severity", ["All", "Critical", "High", "Medium", "Low"])
    overdue_only = st.sidebar.checkbox("Show Overdue / Breached Only", value=False)

    db = get_db_session()
    try:
        incidents, total = IncidentService.list_incidents(
            db,
            search=search_q if search_q else None,
            status_filter=status_filter if status_filter != "All" else None,
            severity_filter=severity_filter if severity_filter != "All" else None,
            is_overdue_filter=True if overdue_only else None,
            page_size=200
        )
    finally:
        db.close()

    st.write(f"Showing **{len(incidents)}** of **{total}** incidents matching criteria.")

    if not incidents:
        st.info("No incidents found matching current filters.")
    else:
        # Table summary
        table_data = []
        for i in incidents:
            table_data.append({
                "Number": i.incident_number,
                "Title": i.title[:50] + ("..." if len(i.title) > 50 else ""),
                "Severity": i.severity,
                "Priority": i.priority,
                "Status": i.status,
                "Service": i.service,
                "Assignee": i.assignee or "Unassigned",
                "Age": i.age_human_readable,
                "SLA Status": i.sla_status,
                "Overdue": "⚠️ BREACHED" if i.is_overdue else "OK"
            })
        
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)

        st.markdown("---")
        st.subheader("🔍 Deep-Dive Incident Inspector & RCA")

        # Select Incident for detail
        incident_choices = [f"{i.incident_number} — {i.title[:60]}" for i in incidents]
        selected_choice = st.selectbox("Select Incident to Inspect:", incident_choices)
        selected_number = selected_choice.split(" — ")[0]

        # Fetch full detail
        db = get_db_session()
        try:
            detail = IncidentService.get_incident_detail(db, selected_number)
        finally:
            db.close()

        # Display details in structured tabs
        det_tab1, det_tab2, det_tab3, det_tab4 = st.tabs([
            "📌 Incident Overview",
            "🔬 Root Cause Analysis (RCA)",
            "📝 Investigation Notes",
            "📜 Audit & Activity Trail"
        ])

        with det_tab1:
            colA, colB, colC = st.columns(3)
            with colA:
                st.write(f"**Incident Number:** `{detail.incident_number}`")
                st.write(f"**Title:** {detail.title}")
                st.write(f"**Service:** `{detail.service}`")
                st.write(f"**Category:** {detail.category}")
            with colB:
                st.write(f"**Status:** `{detail.status}`")
                st.write(f"**Severity:** {detail.severity}")
                st.write(f"**Priority:** {detail.priority}")
                st.write(f"**Assignee:** `{detail.assignee or 'Unassigned'}`")
            with colC:
                st.write(f"**SLA Resolution Target:** `{detail.sla_resolution_target_hours} hours`")
                st.write(f"**Incident Age:** `{detail.age_human_readable}`")
                st.write(f"**SLA Status:** **{detail.sla_status}**")
                st.write(f"**Created At:** {format_iso(detail.created_at)}")
            
            st.write("**Full Description:**")
            st.info(detail.description)

            # Quick Status Transition in UI
            st.markdown("#### Transition Incident Lifecycle")
            with st.expander("Update Status"):
                with st.form("status_transition_form"):
                    new_status = st.selectbox(
                        "Target Status",
                        [s.value for s in IncidentStatusEnum if s.value != detail.status]
                    )
                    transition_reason = st.text_input("Transition Reason / Note")
                    pending_reason = None
                    if new_status == "Pending":
                        pending_reason = st.text_input("Pending Reason (Required for Pending)", value="Awaiting customer input")
                    
                    res_summary = None
                    root_cause_input = None
                    corr_action_input = None
                    if new_status == "Resolved":
                        res_summary = st.text_area("Resolution Summary (Required for Resolved)", value=detail.resolution_summary or "Issue mitigated.")
                        root_cause_input = st.text_area("Root Cause (Optional)", value=detail.root_cause or "")
                        corr_action_input = st.text_area("Corrective Action (Optional)", value=detail.corrective_action or "")

                    submit_status = st.form_submit_button("Submit Status Transition")
                    if submit_status:
                        db = get_db_session()
                        try:
                            req = StatusTransitionRequest(
                                status=IncidentStatusEnum(new_status),
                                reason=transition_reason,
                                pending_reason=pending_reason,
                                resolution_summary=res_summary,
                                root_cause=root_cause_input,
                                corrective_action=corr_action_input,
                            )
                            IncidentService.transition_status(
                                db,
                                identifier=detail.incident_number,
                                payload=req,
                                performed_by="dashboard_operator",
                                user_role=UserRole.ENGINEER
                            )
                            st.success(f"Status updated to '{new_status}' successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Transition failed: {str(e)}")
                        finally:
                            db.close()

        with det_tab2:
            st.subheader("Root Cause Analysis (RCA) Documentation")
            
            if detail.root_cause or detail.corrective_action:
                st.success("✅ Root Cause Analysis has been recorded for this incident.")
                st.markdown(f"**Confirmed Root Cause:**\n> {detail.root_cause or 'N/A'}")
                st.markdown(f"**Immediate Corrective Action:**\n> {detail.corrective_action or 'N/A'}")
                st.markdown(f"**Preventive / Long-term Guardrails:**\n> {detail.preventive_action or 'N/A'}")
                st.markdown(f"**Resolution Summary:**\n> {detail.resolution_summary or 'N/A'}")
            else:
                st.warning("⚠️ RCA has not been documented yet for this incident.")

            st.markdown("---")
            st.markdown("#### Document / Update RCA")
            with st.form("rca_update_form"):
                rc_in = st.text_area("Confirmed Root Cause (Technical details)", value=detail.root_cause or "", height=100)
                ca_in = st.text_area("Corrective Action Taken", value=detail.corrective_action or "", height=100)
                pa_in = st.text_area("Preventive Action (Guardrails, tests, architecture changes)", value=detail.preventive_action or "", height=100)
                rs_in = st.text_area("Resolution Summary", value=detail.resolution_summary or "", height=80)
                
                rca_submit = st.form_submit_button("Save RCA Documentation")
                if rca_submit:
                    if not rc_in or not ca_in:
                        st.error("Root Cause and Corrective Action are required fields.")
                    else:
                        db = get_db_session()
                        try:
                            rca_payload = RcaUpdateRequest(
                                root_cause=rc_in,
                                corrective_action=ca_in,
                                preventive_action=pa_in if pa_in else None,
                                resolution_summary=rs_in if rs_in else None
                            )
                            RcaService.update_rca(
                                db=db,
                                identifier=detail.incident_number,
                                payload=rca_payload,
                                performed_by="dashboard_engineer"
                            )
                            st.success("RCA documentation saved successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving RCA: {str(e)}")
                        finally:
                            db.close()

        with det_tab3:
            st.subheader(f"Investigation Notes ({len(detail.notes)})")
            
            # Form to add new note
            with st.expander("➕ Add New Investigation Note"):
                with st.form("add_note_form"):
                    note_type = st.selectbox("Note Type", [t.value for t in NoteTypeEnum])
                    note_content = st.text_area("Findings / Diagnostics / Logs / Evidence", height=100)
                    note_author = st.text_input("Author", value="dashboard_engineer")
                    note_submit = st.form_submit_button("Add Note")
                    if note_submit:
                        if not note_content:
                            st.error("Note content cannot be empty.")
                        else:
                            db = get_db_session()
                            try:
                                n_payload = InvestigationNoteCreate(
                                    note_type=NoteTypeEnum(note_type),
                                    content=note_content,
                                    author=note_author
                                )
                                RcaService.add_investigation_note(
                                    db=db,
                                    identifier=detail.incident_number,
                                    payload=n_payload,
                                    performed_by=note_author
                                )
                                st.success("Note added successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to add note: {str(e)}")
                            finally:
                                db.close()

            # Render notes timeline
            if detail.notes:
                for note in detail.notes:
                    with st.chat_message("user"):
                        st.markdown(f"**[{note.note_type}]** by `{note.author}` at `{format_iso(note.created_at)}`")
                        st.write(note.content)
            else:
                st.info("No investigation notes recorded yet.")

        with det_tab4:
            st.subheader("Timestamped Activity History & Audit Trail")
            if detail.activities:
                act_data = []
                for a in detail.activities:
                    act_data.append({
                        "Timestamp": format_iso(a.timestamp),
                        "Action": a.action,
                        "Field": a.field_name or "-",
                        "Old Value": a.old_value or "-",
                        "New Value": a.new_value or "-",
                        "Actor": a.performed_by,
                        "Notes": a.notes or ""
                    })
                st.dataframe(pd.DataFrame(act_data), use_container_width=True)
            else:
                st.info("No activity recorded.")

# -------------------------------------------------------------
# TAB 3: LOG NEW INCIDENT
# -------------------------------------------------------------
elif nav_section == "➕ Log New Incident":
    st.title("Create New IT Incident")
    st.caption("Submit an incident to initiate the ITIL lifecycle and start SLA tracking.")

    with st.form("new_incident_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Incident Title *", placeholder="e.g. Payment Gateway High Latency")
            category = st.selectbox("Category *", ["Software", "Database", "Security", "Infrastructure", "Network", "Hardware", "Cloud"])
            severity = st.selectbox("Severity *", ["Critical", "High", "Medium", "Low"], index=2)
            service = st.text_input("Affected Service *", placeholder="e.g. Auth Service, Core DB")
        
        with col2:
            reporter = st.text_input("Reporter *", value="operations_team")
            assignee = st.text_input("Assignee (Optional)", placeholder="e.g. engineer@company.com")
            assignment_group = st.text_input("Assignment Group", value="Site Reliability Engineering")
            sla_custom = st.number_input("Custom SLA Resolution Target (Hours, Optional)", min_value=0.0, max_value=720.0, value=0.0, step=1.0)

        description = st.text_area("Detailed Description *", placeholder="Provide symptoms, error messages, affected user count, and initial logs...", height=150)
        
        submitted = st.form_submit_button("🚀 Submit Incident")
        if submitted:
            if not title or not service or not reporter or not description:
                st.error("Please fill in all required fields (Title, Service, Reporter, Description).")
            else:
                db = get_db_session()
                try:
                    payload = IncidentCreate(
                        title=title,
                        description=description,
                        category=category,
                        severity=SeverityEnum(severity),
                        service=service,
                        reporter=reporter,
                        assignee=assignee if assignee else None,
                        assignment_group=assignment_group if assignment_group else None,
                        sla_resolution_target_hours=sla_custom if sla_custom > 0 else None,
                    )
                    created = IncidentService.create_incident(db, payload, performed_by=reporter)
                    st.success(f"Incident created successfully: **{created.incident_number}**")
                    st.info(f"Assigned Priority: `{created.priority}` | SLA Deadline: `{format_iso(created.sla_deadline)}` ({created.sla_resolution_target_hours}h target)")
                except Exception as e:
                    st.error(f"Failed to create incident: {str(e)}")
                finally:
                    db.close()

# -------------------------------------------------------------
# TAB 4: DATABASE ADMIN
# -------------------------------------------------------------
elif nav_section == "⚙️ Database Admin":
    st.title("Platform Administration & Seed Utility")

    st.markdown("### Database Summary")
    db = get_db_session()
    inc_count = db.query(Incident).count()
    db.close()
    st.write(f"Current Incidents in Database: **{inc_count}**")

    colA, colB = st.columns(2)
    with colA:
        st.subheader("Seed Curated Demo Data")
        st.write("Loads 7 production scenarios covering P1-P4 severities, active/resolved statuses, full RCAs, and SLA compliance variations.")
        if st.button("Load Curated Incidents"):
            db = get_db_session()
            n = seed_curated_data(db)
            db.close()
            st.success(f"Seeded {n} incidents!")
            st.rerun()

    with colB:
        st.subheader("Import Historical CSV Dataset")
        st.write("Ingests real IT incident traces from `incident_event_log.csv` located in this project.")
        import_limit = st.slider("Import Sample Size", min_value=5, max_value=100, value=25)
        if st.button("Import from CSV"):
            csv_path = os.path.join("incident+management+process+enriched+event+log", "incident_event_log.csv")
            db = get_db_session()
            from scripts.seed_data import import_from_csv
            n = import_from_csv(db, csv_path, limit=import_limit)
            db.close()
            st.success(f"Imported {n} incidents from CSV dataset!")
            st.rerun()
