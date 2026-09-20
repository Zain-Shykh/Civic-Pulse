"""Service-layer tests — real Postgres via app.db.engine, no mocks.

Same precedent as test_repositories.py: precondition is `alembic upgrade
head` + the seed script already run; any row a test creates itself is
cleaned up in a `finally`.
"""

import uuid
from typing import Any

import pytest
from sqlalchemy import text

from app.db import engine
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage
from app.repositories import complaints as repository
from app.scripts.seed import _COMPLAINTS
from app.services import complaints as services
from app.services.exceptions import IllegalTransitionError, NotFoundError

_DELETE = text("DELETE FROM complaints WHERE id = :id")


async def _delete(complaint_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(_DELETE, {"id": complaint_id})


async def _make_complaint() -> dict[str, Any]:
    return await repository.create(
        complaint_text="Service layer test complaint, long enough to pass validation.",
        location="Test Location",
        reporter_contact=None,
        category="water",
        priority="normal",
        ai_summary="test",
        triaged_by="rules",
        triage_latency_ms=1,
    )


class TestStateMachine:
    @pytest.mark.parametrize(
        "current,target",
        [
            ("open", "in_progress"),
            ("in_progress", "resolved"),
            ("open", "rejected"),
            ("in_progress", "rejected"),
        ],
    )
    async def test_legal_transitions_succeed(self, current: str, target: str) -> None:
        row = await _make_complaint()
        try:
            if current != "open":
                await repository.update_status(row["id"], current)
            updated = await services.change_status(row["id"], target)
            assert updated["status"] == target
        finally:
            await _delete(row["id"])

    @pytest.mark.parametrize(
        "current,target",
        [
            ("resolved", "open"),
            ("resolved", "in_progress"),
            ("rejected", "open"),
            ("rejected", "in_progress"),
            ("open", "resolved"),
            ("in_progress", "open"),
        ],
    )
    async def test_illegal_transitions_raise(self, current: str, target: str) -> None:
        row = await _make_complaint()
        try:
            if current != "open":
                await repository.update_status(row["id"], current)
            with pytest.raises(IllegalTransitionError) as exc_info:
                await services.change_status(row["id"], target)
            assert exc_info.value.current_status == current
            assert exc_info.value.attempted_status == target
        finally:
            await _delete(row["id"])

    async def test_missing_complaint_raises_not_found(self) -> None:
        missing_id = uuid.uuid4()
        with pytest.raises(NotFoundError) as exc_info:
            await services.change_status(missing_id, "in_progress")
        assert exc_info.value.complaint_id == missing_id


class TestTriageOrchestration:
    async def test_submit_complaint_with_simulated_provider_round_trips(self) -> None:
        created = await services.submit_complaint(
            SimulatedTriage(),
            text="Water pipeline burst near the market, urgent repair needed.",
            location="Test Location",
            reporter_contact=None,
        )
        try:
            assert created["triaged_by"] == "simulated"
            assert created["triage_latency_ms"] >= 0
            assert created["status"] == "open"
        finally:
            await _delete(created["id"])

    async def test_submit_complaint_with_rule_based_provider_round_trips(self) -> None:
        created = await services.submit_complaint(
            RuleBasedTriage(),
            text="Streetlight has been broken for two weeks on our road.",
            location="Test Location",
            reporter_contact=None,
        )
        try:
            assert created["triaged_by"] == "rules"
            assert created["category"] == "streetlights"
        finally:
            await _delete(created["id"])


class TestMandatoryDeterminism:
    """CONTRACTS.md §2.5: 'given a provider that always raises, ...
    triaged_by == "rules:fallback"' — exercised at the service level, one
    layer above the provider-level version already proven in
    test_llm_triage.py's TestMandatoryDeterminism. This is the case that
    motivated the service layer's own fallback wrap: SimulatedTriage has no
    internal fallback of its own (see phase-06-service-layer.md's Plan).
    """

    async def test_provider_that_always_raises_falls_back_deterministically(self) -> None:
        created = await services.submit_complaint(
            SimulatedTriage(always_raise=True),
            text="This complaint's provider is broken on purpose.",
            location="Test Location",
            reporter_contact=None,
        )
        try:
            assert created["triaged_by"] == "rules:fallback"
        finally:
            await _delete(created["id"])


class TestStats:
    async def test_get_stats_matches_seed_distribution(self) -> None:
        stats = await services.get_stats()

        expected_by_status: dict[str, int] = {}
        for row in _COMPLAINTS:
            status = row[5]
            expected_by_status[status] = expected_by_status.get(status, 0) + 1

        for status, count in expected_by_status.items():
            assert stats["counts_by_status"].get(status, 0) >= count
        assert stats["average_triage_latency_ms"] >= 0
