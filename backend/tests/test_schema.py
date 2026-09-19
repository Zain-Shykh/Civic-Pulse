"""First real-DB test in the suite — the pattern future phases follow:
connect directly to the live Postgres named by DATABASE_URL, no mocks, and
assert on actual database behaviour.

Precondition: `alembic upgrade head` must already have been run against
that database. This test only asserts the resulting constraints/indexes
exist — it does not manage migrations itself.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import engine

_INSERT = text(
    """
    INSERT INTO complaints (
        id, text, location, reporter_contact, category, priority,
        status, ai_summary, triaged_by, triage_latency_ms,
        created_at, updated_at
    ) VALUES (
        :id, :text, :location, :reporter_contact, :category, :priority,
        :status, :ai_summary, :triaged_by, :triage_latency_ms,
        :created_at, :updated_at
    )
    """
)


async def test_invalid_category_rejected_by_db() -> None:
    """`category` is a Postgres enum — an out-of-enum value must be rejected
    at the DB level, not only by app-side validation."""
    now = datetime.now(UTC)
    params = {
        "id": uuid.uuid4(),
        "text": "This complaint text is long enough to pass the length check.",
        "location": "Test Location",
        "reporter_contact": None,
        "category": "not_a_real_category",
        "priority": "normal",
        "status": "open",
        "ai_summary": None,
        "triaged_by": "rules",
        "triage_latency_ms": 10,
        "created_at": now,
        "updated_at": now,
    }
    with pytest.raises(DBAPIError):
        async with engine.begin() as conn:
            await conn.execute(_INSERT, params)


async def test_required_indexes_exist() -> None:
    """Both indexes required by CONTRACTS.md (§2.3) / SCHEMA.md must exist."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'complaints'")
        )
        index_names = {row[0] for row in result}

    assert "ix_complaints_status_priority" in index_names
    assert "ix_complaints_created_at" in index_names
