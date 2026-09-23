"""GET /metrics — docs/specs/phase-07b-metrics.md.

Real Postgres via app.db.engine (no mocks), exercised over real HTTP
(fastapi.testclient.TestClient), same precedent as test_routes_complaints.py.
"""

import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.providers.triage.simulated import SimulatedTriage
from app.routes.dependencies import get_triage_provider

_DELETE = text("DELETE FROM complaints WHERE id = :id")


async def _delete(complaint_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(_DELETE, {"id": complaint_id})


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _fallback_total(metrics_text: str) -> float:
    match = re.search(r"^triage_fallback_total\s+(\S+)$", metrics_text, re.MULTILINE)
    assert match, f"triage_fallback_total not found in:\n{metrics_text}"
    return float(match.group(1))


class TestMetricsEndpoint:
    async def test_metrics_returns_all_four_required_metric_families(
        self, client: TestClient
    ) -> None:
        created = client.post(
            "/api/complaints", json={"text": "A" * 20, "location": "Test Location"}
        ).json()
        try:
            response = client.get("/metrics")
            assert response.status_code == 200
            assert "text/plain" in response.headers["content-type"]
            body = response.text
            assert "http_requests_total" in body
            assert "http_request_duration_seconds" in body
            assert "triage_latency_seconds" in body
            assert "triage_fallback_total" in body
        finally:
            await _delete(uuid.UUID(created["id"]))

    async def test_fallback_counter_increments_on_provider_that_always_raises(
        self, client: TestClient
    ) -> None:
        before = _fallback_total(client.get("/metrics").text)

        app.dependency_overrides[get_triage_provider] = lambda: SimulatedTriage(
            always_raise=True
        )
        try:
            response = client.post(
                "/api/complaints", json={"text": "A" * 20, "location": "Test Location"}
            )
            assert response.status_code == 201
            body = response.json()
            try:
                after = _fallback_total(client.get("/metrics").text)
                assert after - before == 1
            finally:
                await _delete(uuid.UUID(body["id"]))
        finally:
            app.dependency_overrides.clear()
