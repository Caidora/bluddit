import pytest
from fastapi.testclient import TestClient

from bluddit_api.main import create_app


def test_health_does_not_require_database_or_expose_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "must-never-appear")
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/api/accounts"])
def test_only_skeleton_api_is_available(path):
    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 404


def test_invalid_environment_is_actionable(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prodution")
    with pytest.raises(RuntimeError, match="APP_ENV must be"):
        create_app()
