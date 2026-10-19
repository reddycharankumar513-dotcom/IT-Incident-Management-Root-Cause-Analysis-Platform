import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database import init_db
from app.logging_config import setup_logging, logger

if __name__ == "__main__":
    setup_logging()
    logger.info("Initializing schema for IT Incident Management Platform...")
    init_db()
    logger.info("Database initialized successfully.")
    print("Database tables initialized successfully.")
