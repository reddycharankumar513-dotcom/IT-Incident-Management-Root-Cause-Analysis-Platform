import os
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, Base, engine
from app.schemas.common import UserRole
from app.security import require_role, AuthenticatedUser
from scripts.seed_data import seed_curated_data, import_from_csv

router = APIRouter(prefix="/seed", tags=["Data Seeding & Migration"])

@router.post(
    "/sample-data",
    status_code=status.HTTP_200_OK,
    summary="Seed curated demo incidents",
    description="Loads realistic production incidents covering P1-P4 severities, active and resolved workflows, RCA notes, and SLA violations."
)
def seed_demo_data(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN])),
):
    count = seed_curated_data(db)
    return {"message": "Curated incidents seeded successfully", "seeded_count": count}

@router.post(
    "/import-csv",
    status_code=status.HTTP_200_OK,
    summary="Import incidents from local CSV dataset",
    description="Imports real historical incident traces from the provided incident_event_log.csv dataset."
)
def import_csv_data(
    limit: int = Query(30, ge=1, le=500, description="Maximum number of unique incidents to import"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN])),
):
    csv_path = os.path.join("incident+management+process+enriched+event+log", "incident_event_log.csv")
    count = import_from_csv(db, csv_path, limit=limit)
    return {"message": "CSV dataset imported successfully", "imported_count": count, "source_file": csv_path}

@router.post(
    "/reset",
    status_code=status.HTTP_200_OK,
    summary="Reset database and re-seed defaults",
    description="Wipes all tables, recreates schema, and seeds default demonstration incidents. (Admin only)."
)
def reset_database(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role([UserRole.ADMIN])),
):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    count = seed_curated_data(db)
    return {"message": "Database reset and re-seeded successfully", "seeded_count": count}
