from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
from app.logging_config import setup_logging, logger
from app.api.v1.incidents import router as incidents_router
from app.api.v1.notes import router as notes_router
from app.api.v1.rca import router as rca_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.seed import router as seed_router
from app.schemas.common import HealthCheck
from app.utils.timezone import utc_now, format_iso

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode...")
    init_db()
    logger.info("Application startup completed.")
    yield
    logger.info("Application shutdown completed.")

app = FastAPI(
    title=settings.APP_NAME,
    description="""
# IT Incident Management & Root Cause Analysis (RCA) Platform

A comprehensive enterprise-grade platform for incident lifecycle management, ITIL workflows, RCA documentation, SLA tracking, and operational metrics.

## Key Capabilities:
- **Incident Lifecycle Management**: Strict ITIL state transitions (`Open` → `In Progress` → `Pending` / `Resolved` → `Closed`).
- **Configurable SLA Engine**: SLA resolution and response targets by severity (Critical: 4h, High: 8h, Medium: 24h, Low: 72h).
- **Overdue & Breach Detection**: Real-time SLA age calculation, breach flagging, and at-risk monitoring.
- **RCA Documentation**: Structured 5-Whys, Root Cause, Corrective Actions, Preventive Actions, and Resolution Summaries.
- **Investigation Notes**: Detailed diagnostic logs, hypotheses, workarounds, and evidence records.
- **Activity History & Audit Trail**: Chronological immutable tracking of every status shift, assignment, and update.
- **Operational & Executive Metrics**: MTTR (Mean Time to Resolve), MTTA, SLA Compliance Rate, and breakdowns by severity/assignee.
- **Role-Based Access Control**: `Admin`, `Engineer`, and `Viewer` roles supporting both HTTP Basic Auth and `X-API-Key` headers.

## Authentication:
- **HTTP Basic Auth**:
  - `admin` : `admin123` (Admin Role)
  - `engineer` : `engineer123` (Engineer Role)
  - `viewer` : `viewer123` (Viewer Role - Read-only)
- **API Key**:
  - Header: `X-API-Key`
  - Admin: `adm-key-secret-999`
  - Engineer: `eng-key-secret-555`
  - Viewer: `view-key-secret-111`
""",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Exception Handlers for clean API error responses
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "message": exc.detail,
            "path": request.url.path,
            "timestamp": format_iso(utc_now()),
        },
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err["loc"])
        errors.append({"field": field, "message": err["msg"], "type": err["type"]})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": "Validation error in request payload or query parameters",
            "details": errors,
            "path": request.url.path,
            "timestamp": format_iso(utc_now()),
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "An internal server error occurred. Sensitive details have been logged securely.",
            "path": request.url.path,
            "timestamp": format_iso(utc_now()),
        },
    )

# Root and Health Endpoints
@app.get(
    "/",
    tags=["General"],
    summary="Root Service Information",
    description="Returns platform overview, API version, and links to documentation."
)
def root():
    return {
        "platform": settings.APP_NAME,
        "version": "2.0.0",
        "documentation": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "api_v1_prefix": "/api/v1",
        "server_time_utc": format_iso(utc_now()),
    }

@app.get(
    "/health",
    response_model=HealthCheck,
    tags=["General"],
    summary="Health check",
    description="Returns service availability and environment status."
)
def health():
    return HealthCheck(
        status="healthy",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        timestamp=format_iso(utc_now()),
    )

# Register v1 Routers
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(notes_router, prefix="/api/v1")
app.include_router(rca_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(seed_router, prefix="/api/v1")
