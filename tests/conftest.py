import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database import Base, get_db
from app.main import app
from app.config import settings

# In-memory SQLite for high-speed, isolated test execution
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure AUTH_ENABLED is True during test suite execution."""
    settings.AUTH_ENABLED = True
    yield

@pytest.fixture(scope="function")
def db_session():
    """Creates a fresh database schema for each test function."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """TestClient that uses the isolated in-memory test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def admin_headers():
    return {"X-API-Key": settings.API_KEY_ADMIN}

@pytest.fixture
def engineer_headers():
    return {"X-API-Key": settings.API_KEY_ENGINEER}

@pytest.fixture
def viewer_headers():
    return {"X-API-Key": settings.API_KEY_VIEWER}

@pytest.fixture
def basic_auth_admin():
    import base64
    token = base64.b64encode(b"admin:admin123").decode("utf-8")
    return {"Authorization": f"Basic {token}"}

@pytest.fixture
def basic_auth_engineer():
    import base64
    token = base64.b64encode(b"engineer:engineer123").decode("utf-8")
    return {"Authorization": f"Basic {token}"}

@pytest.fixture
def basic_auth_viewer():
    import base64
    token = base64.b64encode(b"viewer:viewer123").decode("utf-8")
    return {"Authorization": f"Basic {token}"}
