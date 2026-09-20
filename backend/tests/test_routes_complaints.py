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

from app.db import engine
from app.main import app
from app.providers.triage.simulated import SimulatedTriage
from app.repositories import complaints as repository
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
            response = client.post("/api/complaints", json=_create_payload())
            assert response.status_code == 201
            body = response.json()
            try:
                assert body["triaged_by"] == "rules:fallback"
            finally:
                await _delete(uuid.UUID(body["id"]))
        finally:
            app.dependency_overrides.clear()
