"""Smoke test for the walking skeleton: /health always 200, /ready reflects
dependency reachability. Not the real backend test suite (that arrives with
services/repositories); this only proves the container-level plumbing works.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_always_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_when_dependencies_up() -> None:
    with (
        patch("app.routes.health.db_ping", new=AsyncMock(return_value=True)),
        patch("app.routes.health.redis_ping", new=AsyncMock(return_value=True)),
    ):
        resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_ready_names_failed_dependency() -> None:
    with (
        patch("app.routes.health.db_ping", new=AsyncMock(return_value=False)),
        patch("app.routes.health.redis_ping", new=AsyncMock(return_value=True)),
    ):
        resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["failed_dependencies"] == ["postgres"]
