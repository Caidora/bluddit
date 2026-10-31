from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from bluddit_api.main import create_app
from bluddit_api.utils.dependencies import get_health_repository


def test_health_does_not_require_database_or_expose_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "must-never-appear")
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentation_is_not_served_outside_api_prefix(path):
    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("environment", ["development", "test", "production"])
def test_swagger_and_schema_are_available_under_api_prefix(monkeypatch, environment):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("PGHOST", "localhost")
    monkeypatch.setenv("PGDATABASE", "bluddit_test")
    monkeypatch.setenv("PGUSER", "bluddit")
    monkeypatch.setenv("PGPASSWORD", "test-password")
    monkeypatch.delenv("PGPASSWORD_FILE", raising=False)
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "https://bluddit.example")
    # Documentation does not require the database pool or application lifespan.
    client = TestClient(create_app())
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "SwaggerUIBundle" in response.text
    assert "/api/openapi.json" in response.text
    assert "/api/docs/oauth2-redirect" in response.text
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    assert schema.json()["info"]["title"] == "Bluddit API"
    assert "/api/health" in schema.json()["paths"]
    assert "/api/auth/login" in schema.json()["paths"]


def test_invalid_environment_is_actionable(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prodution")
    with pytest.raises(RuntimeError, match="APP_ENV must be"):
        create_app()


def test_readiness_without_database_preserves_unavailable_response(monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.parametrize("is_ready", [True, False])
def test_readiness_accepts_repository_override(monkeypatch, is_ready):
    monkeypatch.delenv("PGHOST", raising=False)
    repository = AsyncMock()
    repository.is_ready.return_value = is_ready
    app = create_app()
    app.dependency_overrides[get_health_repository] = lambda: repository
    with TestClient(app) as client:
        response = client.get("/api/ready")
    assert response.status_code == (200 if is_ready else 503)
    assert response.json() == {"status": "ok" if is_ready else "unavailable"}
    repository.is_ready.assert_awaited_once_with(app.state.migrations)
