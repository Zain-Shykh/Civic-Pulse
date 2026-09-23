"""HTTP-level tests — docs/specs/phase-07-routes.md.

Real Postgres via app.db.engine (same precedent as test_repositories.py /
test_services_complaints.py, no mocks), but exercised through the actual
FastAPI app over HTTP (fastapi.testclient.TestClient), not by calling
services/repositories functions directly. TestClient used as a context
manager so the app's lifespan (which constructs the TriageProvider onto
app.state) actually runs.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.main import app
from app.providers import cache
from app.providers.triage.simulated import SimulatedTriage
from app.repositories import complaints as repository
from app.routes.dependencies import get_triage_provider


async def _flush_rate_limit(client_ip: str) -> None:
    keys = [key async for key in cache.client.scan_iter(f"ratelimit:{client_ip}:*")]
    if keys:
        await cache.client.delete(*keys)

_DELETE = text("DELETE FROM complaints WHERE id = :id")

# Every test in this file shares this TestClient's default
# request.client.host ("testclient") unless overridden — since Phase 8 wires
# a real per-IP rate limiter behind POST /api/complaints, every HTTP-level
# test file needs its own fixed, distinct X-Real-IP so it doesn't share a
# rate-limit bucket with any other file (docs/specs/phase-08-cache-layer.md's
# Plan, "Test isolation for the rate limiter").
_FILE_CLIENT_IP = "10.0.0.11"


async def _delete(complaint_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(_DELETE, {"id": complaint_id})


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, headers={"X-Real-IP": _FILE_CLIENT_IP}) as c:
        yield c
    app.dependency_overrides.clear()


def _create_payload(
    text_body: str = "A pothole has appeared on the main road near the market.",
) -> dict[str, str]:
    return {"text": text_body, "location": "Test Location"}


class TestCreateAndFetch:
    async def test_create_then_get_round_trips(self, client: TestClient) -> None:
        response = client.post("/api/complaints", json=_create_payload())
        assert response.status_code == 201
        body = response.json()
        try:
            assert body["status"] == "open"
            fetched = client.get(f"/api/complaints/{body['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["id"] == body["id"]
        finally:
            await _delete(uuid.UUID(body["id"]))

    async def test_get_missing_id_returns_404(self, client: TestClient) -> None:
        response = client.get(f"/api/complaints/{uuid.uuid4()}")
        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_create_with_short_text_returns_400(self, client: TestClient) -> None:
        response = client.post("/api/complaints", json=_create_payload(text_body="too short"))
        assert response.status_code == 400
        assert "detail" in response.json()


class TestStateMachineOverHttp:
    @pytest.mark.parametrize(
        "current,target",
        [
            ("open", "in_progress"),
            ("in_progress", "resolved"),
            ("open", "rejected"),
            ("in_progress", "rejected"),
        ],
    )
    async def test_legal_transitions_return_200(
        self, client: TestClient, current: str, target: str
    ) -> None:
        created = await repository.create(
            complaint_text="Route-level state machine test complaint, long enough.",
            location="Test Location",
            reporter_contact=None,
            category="water",
            priority="normal",
            ai_summary="test",
            triaged_by="rules",
            triage_latency_ms=1,
        )
        try:
            if current != "open":
                await repository.update_status(created["id"], current)
            response = client.patch(
                f"/api/complaints/{created['id']}/status", json={"status": target}
            )
            assert response.status_code == 200
            assert response.json()["status"] == target
        finally:
            await _delete(created["id"])

    @pytest.mark.parametrize(
        "current,target",
        [("resolved", "open"), ("open", "resolved"), ("in_progress", "open")],
    )
    async def test_illegal_transitions_return_409_naming_transition(
        self, client: TestClient, current: str, target: str
    ) -> None:
        created = await repository.create(
            complaint_text="Route-level illegal transition test complaint, long enough.",
            location="Test Location",
            reporter_contact=None,
            category="water",
            priority="normal",
            ai_summary="test",
            triaged_by="rules",
            triage_latency_ms=1,
        )
        try:
            if current != "open":
                await repository.update_status(created["id"], current)
            response = client.patch(
                f"/api/complaints/{created['id']}/status", json={"status": target}
            )
            assert response.status_code == 409
            detail = response.json()["detail"]
            assert detail["current_status"] == current
            assert detail["attempted_status"] == target
        finally:
            await _delete(created["id"])

    async def test_status_update_missing_id_returns_404(self, client: TestClient) -> None:
        response = client.patch(
            f"/api/complaints/{uuid.uuid4()}/status", json={"status": "in_progress"}
        )
        assert response.status_code == 404


class TestListAndPagination:
    async def test_page_size_over_100_rejected(self, client: TestClient) -> None:
        response = client.get("/api/complaints", params={"page_size": 101})
        assert response.status_code == 400

    async def test_list_returns_items_and_total(self, client: TestClient) -> None:
        response = client.get("/api/complaints", params={"page": 1, "page_size": 5})
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"items", "total", "page", "page_size"}
        assert len(body["items"]) <= 5


class TestMetaAndStats:
    async def test_meta_providers_returns_active_provider_and_outcomes(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/meta/providers")
        assert response.status_code == 200
        body = response.json()
        assert body["active_provider"]
        assert isinstance(body["recent_outcomes"], list)

    async def test_stats_returns_aggregates(self, client: TestClient) -> None:
        response = client.get("/api/stats")
        assert response.status_code == 200
        body = response.json()
        assert "counts_by_status" in body
        assert "average_triage_latency_ms" in body


class TestMandatoryDeterminism:
    """CONTRACTS.md §2.5: 'given a provider that always raises, POST
    /api/complaints still returns 201 and triaged_by == "rules:fallback"' —
    proven for the first time over real HTTP, through the actual app the
    Determinism test's wording is about."""

    async def test_provider_that_always_raises_still_returns_201(
        self, client: TestClient
    ) -> None:
        app.dependency_overrides[get_triage_provider] = lambda: SimulatedTriage(
            always_raise=True
        )
        try:
            # Deliberately NOT _create_payload()'s shared default text: Phase
            # 8's triage-result cache (docs/specs/phase-08-cache-layer.md)
            # means an earlier test's successful (non-fallback) submission of
            # that exact text+location would be replayed here as a cache hit,
            # never actually exercising this provider override.
            response = client.post(
                "/api/complaints",
                json=_create_payload(
                    text_body="This complaint's provider is broken on purpose, "
                    "mandatory determinism check over HTTP."
                ),
            )
            assert response.status_code == 201
            body = response.json()
            try:
                assert body["triaged_by"] == "rules:fallback"
            finally:
                await _delete(uuid.UUID(body["id"]))
        finally:
            app.dependency_overrides.clear()


class TestRateLimiting:
    """docs/specs/phase-08-cache-layer.md, Deliverable (b). Uses its own
    dedicated IP (10.0.0.12), distinct from _FILE_CLIENT_IP (10.0.0.11) that
    every other test in this file shares — driving this bucket over its
    limit must not affect any other test."""

    _IP = "10.0.0.12"

    async def test_exceeding_the_window_returns_429_with_retry_after(self) -> None:
        await _flush_rate_limit(self._IP)
        created_ids: list[uuid.UUID] = []
        try:
            with TestClient(app, headers={"X-Real-IP": self._IP}) as c:
                for _ in range(settings.rate_limit_max):
                    response = c.post("/api/complaints", json=_create_payload())
                    assert response.status_code == 201
                    created_ids.append(uuid.UUID(response.json()["id"]))

                over_limit = c.post("/api/complaints", json=_create_payload())
                assert over_limit.status_code == 429
                retry_after = over_limit.headers.get("retry-after")
                assert retry_after is not None
                assert int(retry_after) > 0
        finally:
            for complaint_id in created_ids:
                await _delete(complaint_id)
            await _flush_rate_limit(self._IP)
