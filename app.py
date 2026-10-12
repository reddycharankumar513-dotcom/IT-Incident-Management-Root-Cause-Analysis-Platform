from contextlib import asynccontextmanager
from datetime import datetime, timezone
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

DB_PATH = "incidents.db"

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@asynccontextmanager
async def lifespan(app: FastAPI):
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                service TEXT NOT NULL,
                root_cause TEXT DEFAULT '',
                resolution TEXT DEFAULT '',
                owner TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    yield

app = FastAPI(
    title="IT Incident Management & RCA API",
    description="Educational API for incident tracking, root-cause notes, and incident trend analysis.",
    version="1.0.0",
    lifespan=lifespan
)

class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=3, max_length=3000)
    severity: str = Field(default="Medium", pattern="^(Critical|High|Medium|Low)$")
    service: str = Field(min_length=2, max_length=100)
    owner: str = Field(default="", max_length=100)

class IncidentUpdate(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(Open|In Progress|Resolved|Closed)$")
    root_cause: Optional[str] = Field(default=None, max_length=3000)
    resolution: Optional[str] = Field(default=None, max_length=3000)
    owner: Optional[str] = Field(default=None, max_length=100)

def row_to_dict(row):
    return dict(row) if row else None

@app.get("/")
def root():
    return {"message": "IT Incident Management & RCA API", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/incidents", status_code=201)
def create_incident(payload: IncidentCreate):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO incidents
            (title, description, severity, status, service, root_cause, resolution, owner, created_at, updated_at)
            VALUES (?, ?, ?, 'Open', ?, '', '', ?, ?, ?)
        """, (payload.title, payload.description, payload.severity, payload.service, payload.owner, now, now))
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row_to_dict(row)

@app.get("/incidents")
def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    service: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500)
):
    query = "SELECT * FROM incidents WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"; params.append(status)
    if severity:
        query += " AND severity = ?"; params.append(severity)
    if service:
        query += " AND service LIKE ?"; params.append(f"%{service}%")
    query += " ORDER BY created_at DESC LIMIT ?"; params.append(limit)
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(r) for r in rows]

@app.get("/incidents/{incident_id}")
def get_incident(incident_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    return row_to_dict(row)

@app.patch("/incidents/{incident_id}")
def update_incident(incident_id: int, payload: IncidentUpdate):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Provide at least one field to update")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    allowed = {"status", "root_cause", "resolution", "owner", "updated_at"}
    if not set(changes).issubset(allowed):
        raise HTTPException(status_code=400, detail="Unsupported field")
    with connect() as conn:
        exists = conn.execute("SELECT id FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Incident not found")
        assignments = ", ".join(f"{key} = ?" for key in changes)
        conn.execute(f"UPDATE incidents SET {assignments} WHERE id = ?",
                     [*changes.values(), incident_id])
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    return row_to_dict(row)

@app.get("/reports/summary")
def report_summary():
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        open_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE status IN ('Open','In Progress')").fetchone()[0]
        severity_rows = conn.execute(
            "SELECT severity, COUNT(*) AS count FROM incidents GROUP BY severity ORDER BY count DESC"
        ).fetchall()
        service_rows = conn.execute(
            "SELECT service, COUNT(*) AS count FROM incidents GROUP BY service ORDER BY count DESC"
        ).fetchall()
        unresolved = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE status != 'Resolved' AND status != 'Closed' AND severity IN ('Critical','High')"
        ).fetchone()[0]
    return {
        "total_incidents": total,
        "open_or_in_progress": open_count,
        "unresolved_critical_or_high": unresolved,
        "by_severity": [dict(r) for r in severity_rows],
        "by_service": [dict(r) for r in service_rows]
    }
