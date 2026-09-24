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
from app.providers import cache
from app.providers.triage.simulated import SimulatedTriage
from app.routes.dependencies import get_triage_provider

_DELETE = text("DELETE FROM complaints WHERE id = :id")
# Distinct from every other test file's fixed IP (docs/specs/
# phase-08-cache-layer.md's Plan, "Test isolation for the rate limiter") —
# this file also POSTs to /api/complaints.
_FILE_CLIENT_IP = "10.0.0.13"


async def _delete(complaint_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(_DELETE, {"id": complaint_id})


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, headers={"X-Real-IP": _FILE_CLIENT_IP}) as c:
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
            # Not this file's other test's "A" * 20 + "Test Location" —
            # Phase 8's triage-result cache (docs/specs/
            # phase-08-cache-layer.md) would replay that test's earlier
            # non-fallback result as a cache hit here, never exercising this
            # always-raising provider override.
            response = client.post(
                "/api/complaints",
                json={
                    "text": "A" * 15 + " unique fallback-counter-increments complaint",
                    "location": "Test Location",
                },
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


class TestLiveFallbackVsCacheReplay:
    """docs/specs/phase-08-cache-layer.md's Plan correction (2026-09-23):
    TRIAGE_FALLBACK_TOTAL must increment only on a LIVE fallback — a
    triage-cache replay of an earlier fallback result must not increment
    it again, even though the replayed row's triaged_by is still honestly
    "rules:fallback"."""

    async def test_cache_replay_of_a_fallback_does_not_double_count(
        self, client: TestClient
    ) -> None:
        text_body = "A" * 20 + " unique fallback-replay-does-not-double-count complaint"
        location = "Fallback Replay Test Location"
        await cache.client.delete(cache._triage_cache_key(text_body, location))

        app.dependency_overrides[get_triage_provider] = lambda: SimulatedTriage(
            always_raise=True
        )
        created_ids: list[uuid.UUID] = []
        try:
            before_first = _fallback_total(client.get("/metrics").text)
            first = client.post(
                "/api/complaints", json={"text": text_body, "location": location}
            )
            assert first.status_code == 201
            first_body = first.json()
            created_ids.append(uuid.UUID(first_body["id"]))
            after_first = _fallback_total(client.get("/metrics").text)
            assert after_first - before_first == 1

            second = client.post(
                "/api/complaints", json={"text": text_body, "location": location}
            )
            assert second.status_code == 201
            second_body = second.json()
            created_ids.append(uuid.UUID(second_body["id"]))
            assert second_body["triaged_by"] == "rules:fallback"
            after_second = _fallback_total(client.get("/metrics").text)
            assert after_second - after_first == 0
        finally:
            for complaint_id in created_ids:
                await _delete(complaint_id)
            app.dependency_overrides.clear()
            await cache.client.delete(cache._triage_cache_key(text_body, location))
