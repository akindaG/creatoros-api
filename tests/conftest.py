import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/creatoros_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:9")
os.environ.setdefault("OLLAMA_TIMEOUT_SECONDS", "0.2")
os.environ.setdefault("AI_FALLBACK_ENABLED", "true")
os.environ.setdefault("SOCIAL_PUBLISH_MODE", "simulate")

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.core.database import Base, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def database_schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    payload = {"name": "Test Creator", "email": "creator@example.com", "password": "StrongPass123"}
    response = client.post("/api/v1/auth/register", json=payload)
    if response.status_code not in {201, 409}:
        raise AssertionError(response.text)
    token = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
