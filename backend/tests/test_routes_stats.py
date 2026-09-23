"""GET /api/stats — docs/specs/phase-08-cache-layer.md, Deliverable (a).

Real Postgres + real Redis (no mocks), exercised over real HTTP, same
precedent as test_routes_complaints.py / test_routes_metrics.py.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.providers import cache

_DELETE = text("DELETE FROM complaints WHERE id = :id")
# Distinct from every other test file's fixed IP (docs/specs/
# phase-08-cache-layer.md's Plan, "Test isolation for the rate limiter") —
# this file also POSTs to /api/complaints to prove invalidation-on-write.
_FILE_CLIENT_IP = "10.0.0.14"


async def _delete(complaint_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(_DELETE, {"id": complaint_id})


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, headers={"X-Real-IP": _FILE_CLIENT_IP}) as c:
        yield c
    app.dependency_overrides.clear()


class TestStatsCache:
    async def test_miss_then_hit_then_invalidated_on_write(self, client: TestClient) -> None:
        await cache.invalidate_stats_cache()

        first = client.get("/api/stats")
        assert first.status_code == 200
        assert first.headers["x-cache"] == "MISS"
        first_data = first.json()

        second = client.get("/api/stats")
        assert second.status_code == 200
        assert second.headers["x-cache"] == "HIT"
        assert second.json() == first_data

        created = client.post(
            "/api/complaints",
            json={
                "text": "A stats-cache invalidation-on-write test complaint.",
                "location": "Stats Test Location",
            },
        ).json()
        try:
            third = client.get("/api/stats")
            assert third.status_code == 200
            assert third.headers["x-cache"] == "MISS"
            third_data = third.json()
            assert (
                third_data["counts_by_status"]["open"]
                == first_data["counts_by_status"].get("open", 0) + 1
            )
        finally:
            await _delete(uuid.UUID(created["id"]))
