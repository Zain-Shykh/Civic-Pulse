"""Repository layer for the `complaints` table.

This is the ONLY place in the codebase allowed to run raw SQL/ORM queries
against `complaints`, per CLAUDE.md's four-layer rule. Everything here
executes exactly what it's given — no business rules.

In particular: `update_status()` writes the status value it receives
verbatim, with no legality check. Whether e.g. `open -> resolved` is a
legal transition is the state machine's job, in the Service layer above
this one, not this file's.

Rows are returned as plain dicts (via `.mappings()`) — no ORM models exist
yet; that's a decision for whichever later phase needs it, not this one.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from app.db import engine

_CREATE = text(
    """
    INSERT INTO complaints (
        text, location, reporter_contact, category, priority,
        ai_summary, triaged_by, triage_latency_ms
    ) VALUES (
        :text, :location, :reporter_contact, :category, :priority,
        :ai_summary, :triaged_by, :triage_latency_ms
    )
    RETURNING *
    """
)

_GET_BY_ID = text("SELECT * FROM complaints WHERE id = :id")

_UPDATE_STATUS = text(
    """
    UPDATE complaints
    SET status = :status, updated_at = now()
    WHERE id = :id
    RETURNING *
    """
)

async def create(
    *,
    complaint_text: str,
    location: str,
    reporter_contact: str | None,
    category: str,
    priority: str,
    ai_summary: str | None,
    triaged_by: str,
    triage_latency_ms: int,
) -> dict[str, Any]:
    """Insert a new complaint. `id` (gen_random_uuid()), `status` (defaults
    to 'open'), `created_at`, `updated_at` are all DB-generated/defaulted —
    never passed in here."""
    async with engine.begin() as conn:
        result = await conn.execute(
            _CREATE,
            {
                "text": complaint_text,
                "location": location,
                "reporter_contact": reporter_contact,
                "category": category,
                "priority": priority,
                "ai_summary": ai_summary,
                "triaged_by": triaged_by,
                "triage_latency_ms": triage_latency_ms,
            },
        )
        return dict(result.mappings().one())


async def get_by_id(complaint_id: uuid.UUID) -> dict[str, Any] | None:
    async with engine.connect() as conn:
        result = await conn.execute(_GET_BY_ID, {"id": complaint_id})
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None


async def list_complaints(
    *,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Filter by any combination of status/category/priority (all optional),
    ordered by created_at DESC (docs/architecture/SCHEMA.md's justification
    for the created_at index). Returns (rows, total) where total is the
    count matching the filters, not the whole table.

    CONTRACTS.md caps page_size at 100 — that's a route-layer validation
    concern (like the request body's field validation); this function
    executes whatever page/page_size it's given.
    """
    filter_values = {"status": status, "category": category, "priority": priority}
    active = {col: val for col, val in filter_values.items() if val is not None}
    where = (
        "WHERE " + " AND ".join(f"{col} = :{col}" for col in active) if active else ""
    )

    async with engine.connect() as conn:
        total = (
            await conn.execute(text(f"SELECT count(*) FROM complaints {where}"), active)
        ).scalar_one()

        offset = (page - 1) * page_size
        rows = await conn.execute(
            text(
                f"SELECT * FROM complaints {where} "
                "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {**active, "limit": page_size, "offset": offset},
        )
        return [dict(row) for row in rows.mappings().all()], total


async def update_status(complaint_id: uuid.UUID, status: str) -> dict[str, Any] | None:
    """Write `status` verbatim and bump `updated_at`. Returns the updated
    row, or None if `complaint_id` doesn't exist. No transition-legality
    check — see module docstring."""
    async with engine.begin() as conn:
        result = await conn.execute(_UPDATE_STATUS, {"id": complaint_id, "status": status})
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None


async def stats_summary() -> dict[str, Any]:
    """Counts by status, counts by category, and average triage latency
    across all complaints.

    CONTRACTS.md (§2.2) requires GET /api/stats to serve "aggregates" but
    doesn't pin an exact response JSON shape — only this repository's raw
    aggregate data is in scope here. The response shape, Redis caching
    (30s TTL), and X-Cache header are Service/route concerns for a later
    phase.
    """
    async with engine.connect() as conn:
        by_status = await conn.execute(
            text("SELECT status, count(*) AS n FROM complaints GROUP BY status")
        )
        by_category = await conn.execute(
            text("SELECT category, count(*) AS n FROM complaints GROUP BY category")
        )
        avg_latency = (
            await conn.execute(text("SELECT avg(triage_latency_ms) FROM complaints"))
        ).scalar_one()

    return {
        "counts_by_status": {row.status: row.n for row in by_status},
        "counts_by_category": {row.category: row.n for row in by_category},
        "average_triage_latency_ms": float(avg_latency) if avg_latency is not None else 0.0,
    }
