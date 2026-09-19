"""Repository-layer tests against the real Postgres — same pattern as
test_schema.py: no mocks, connect to the live DB via app.db.engine.

Precondition: `alembic upgrade head` and the seed script have already been
run against that database (36 seed complaints present, per
app/scripts/seed.py). Tests that insert their own rows clean them up so the
table's contents stay exactly the seed set for tests that depend on that
(list filtering, stats).
"""

import uuid
from collections import Counter

import pytest
from sqlalchemy import text

from app.db import engine
from app.repositories import complaints
from app.scripts.seed import _COMPLAINTS

_DELETE = text("DELETE FROM complaints WHERE id = :id")


async def _delete(complaint_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(_DELETE, {"id": complaint_id})


async def test_create_then_get_by_id_round_trips() -> None:
    created = await complaints.create(
        complaint_text="Test complaint text long enough to pass the check.",
        location="Test Location",
        reporter_contact="0300-0000000",
        category="water",
        priority="high",
        ai_summary="Test summary",
        triaged_by="rules",
        triage_latency_ms=42,
    )
    try:
        assert created["status"] == "open"
        assert created["id"] is not None

        fetched = await complaints.get_by_id(created["id"])
        assert fetched is not None
        assert fetched["text"] == "Test complaint text long enough to pass the check."
        assert fetched["category"] == "water"
        assert fetched["priority"] == "high"
        assert fetched["triage_latency_ms"] == 42
    finally:
        await _delete(created["id"])


async def test_get_by_id_missing_returns_none() -> None:
    assert await complaints.get_by_id(uuid.uuid4()) is None


async def test_list_filters_by_category() -> None:
    rows, total = await complaints.list_complaints(category="water", page_size=100)
    expected = sum(1 for c in _COMPLAINTS if c[3] == "water")
    assert total == expected
    assert len(rows) == expected
    assert all(row["category"] == "water" for row in rows)


async def test_list_filters_by_status_and_priority_combined() -> None:
    rows, total = await complaints.list_complaints(
        status="open", priority="high", page_size=100
    )
    expected = sum(1 for c in _COMPLAINTS if c[5] == "open" and c[4] == "high")
    assert total == expected
    assert all(row["status"] == "open" and row["priority"] == "high" for row in rows)


async def test_list_pagination_covers_all_rows_without_duplicates() -> None:
    seen_ids = set()
    page = 1
    page_size = 10
    total = None
    while True:
        rows, total = await complaints.list_complaints(page=page, page_size=page_size)
        if not rows:
            break
        for row in rows:
            assert row["id"] not in seen_ids, "pagination duplicated a row"
            seen_ids.add(row["id"])
        page += 1

    assert total == len(_COMPLAINTS)
    assert len(seen_ids) == len(_COMPLAINTS)


async def test_update_status_writes_value_and_bumps_updated_at() -> None:
    created = await complaints.create(
        complaint_text="Another test complaint long enough to pass the check.",
        location="Test Location 2",
        reporter_contact=None,
        category="roads",
        priority="normal",
        ai_summary=None,
        triaged_by="rules",
        triage_latency_ms=10,
    )
    try:
        updated = await complaints.update_status(created["id"], "in_progress")
        assert updated is not None
        assert updated["status"] == "in_progress"
        assert updated["updated_at"] > created["updated_at"]
    finally:
        await _delete(created["id"])


async def test_update_status_missing_returns_none() -> None:
    assert await complaints.update_status(uuid.uuid4(), "in_progress") is None


async def test_stats_summary_matches_hand_counted_seed_data() -> None:
    expected_by_status = dict(Counter(c[5] for c in _COMPLAINTS))
    expected_by_category = dict(Counter(c[3] for c in _COMPLAINTS))
    expected_avg_latency = sum(c[8] for c in _COMPLAINTS) / len(_COMPLAINTS)

    result = await complaints.stats_summary()

    assert result["counts_by_status"] == expected_by_status
    assert result["counts_by_category"] == expected_by_category
    assert result["average_triage_latency_ms"] == pytest.approx(expected_avg_latency)
