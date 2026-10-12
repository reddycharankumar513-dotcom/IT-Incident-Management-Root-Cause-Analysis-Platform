# Project A — IT Incident Management & Root Cause Analysis Platform

## Problem statement
IT support teams receive application failures, API errors, and database or service outages. When incidents are tracked inconsistently, it becomes harder to prioritize work, see recurring failures, document root causes, and verify resolution.

## Existing solution
Teams often use spreadsheets, email/chat threads, monitoring alerts, and enterprise IT service-management platforms. These can be effective, but fragmented records or manual reporting can make trend analysis and consistent RCA documentation difficult. Enterprise platforms such as ServiceNow are established solutions; this project is a small educational prototype, not a replacement.

## Proposed solution
Build a REST API that records incidents, tracks severity and status, stores root-cause and resolution notes, and produces summary reports by severity and service.

## Features
- Create, list, filter, and retrieve incidents
- Update status, owner, root-cause notes, and resolution
- Summary report for open incidents and severity/service trends
- SQLite persistence
- Interactive Swagger API documentation

## Run
```bash
python -m venv .venv
# Activate the environment, then:
pip install -r requirements.txt
uvicorn app:app --reload
```
Open `http://127.0.0.1:8000/docs`.

## Try it
Create an incident with `POST /incidents`:
```json
{
  "title": "Payments API timeout",
  "description": "Requests to the payments service time out intermittently.",
  "severity": "High",
  "service": "Payments API",
  "owner": "Platform Support"
}
```
Then use `GET /incidents`, `PATCH /incidents/{id}`, and `GET /reports/summary`.

## RCA workflow
1. Record symptoms and evidence.
2. Investigate logs, recent changes, and dependencies.
3. Write the confirmed root cause separately from hypotheses.
4. Record the corrective action and validation.
5. Resolve the incident and check for recurrence.

## Limitations and next steps
No authentication, role-based access, SLA scheduler, email notifications, audit log, or ServiceNow integration is included. Add these only after the basic API is tested. Do not store real customer or confidential production data.
