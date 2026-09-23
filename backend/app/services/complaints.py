"""Service layer for complaints — docs/specs/phase-06-service-layer.md.

Owns the two things routes/ (Phase 7) must not: the status state-machine
legality check (docs/CONTRACTS.md §2.2 — the repository writes any status
it's given verbatim, by design, see repositories/complaints.py's docstring)
and triage orchestration, including the fallback safety net not every
TriageProvider implementation guarantees on its own (see this phase's Plan,
"Why the service layer needs its own fallback wrap").
"""

import logging
import time
import uuid
from typing import Any

from app.providers.triage.base import TriageProvider, TriageResult
from app.providers.triage.rules import RuleBasedTriage
from app.repositories import complaints as repository
from app.services.exceptions import IllegalTransitionError, NotFoundError

logger = logging.getLogger(__name__)

_LEGAL_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("open", "in_progress"),
        ("in_progress", "resolved"),
        ("open", "rejected"),
        ("in_progress", "rejected"),
    }
)


async def change_status(complaint_id: uuid.UUID, new_status: str) -> dict[str, Any]:
    complaint = await repository.get_by_id(complaint_id)
    if complaint is None:
        raise NotFoundError(complaint_id)

    current_status = complaint["status"]
    if (current_status, new_status) not in _LEGAL_TRANSITIONS:
        raise IllegalTransitionError(current_status, new_status)

    updated = await repository.update_status(complaint_id, new_status)
    # No DELETE endpoint exists anywhere in docs/CONTRACTS.md's API table, so a
    # complaint present at the get_by_id check above cannot be deleted before
    # update_status() runs — this is a provable invariant, not a hedge.
    assert updated is not None
    return updated


async def submit_complaint(
    provider: TriageProvider, *, text: str, location: str, reporter_contact: str | None
) -> dict[str, Any]:
    start = time.monotonic()
    try:
        result = await provider.triage(text, location)
    except Exception:
        logger.warning("triage_provider_raised_falling_back", extra={"provider": provider.name})
        fallback = await RuleBasedTriage().triage(text, location)
        result = TriageResult(
            category=fallback.category,
            priority=fallback.priority,
            summary=fallback.summary,
            confidence=fallback.confidence,
            triaged_by="rules:fallback",
        )
    triage_latency_ms = int((time.monotonic() - start) * 1000)

    created = await repository.create(
        complaint_text=text,
        location=location,
        reporter_contact=reporter_contact,
        category=result.category.value,
        priority=result.priority.value,
        ai_summary=result.summary,
        triaged_by=result.triaged_by,
        triage_latency_ms=triage_latency_ms,
    )
    return {**created, "used_fallback": result.triaged_by == "rules:fallback"}


async def get_stats() -> dict[str, Any]:
    return await repository.stats_summary()


async def get_complaint(complaint_id: uuid.UUID) -> dict[str, Any]:
    complaint = await repository.get_by_id(complaint_id)
    if complaint is None:
        raise NotFoundError(complaint_id)
    return complaint


async def list_complaints(
    *,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    return await repository.list_complaints(
        status=status, category=category, priority=priority, page=page, page_size=page_size
    )


async def get_meta_providers(provider: TriageProvider) -> dict[str, Any]:
    outcomes = await repository.recent_triage_outcomes(limit=20)
    return {
        "active_provider": provider.name,
        "recent_outcomes": [
            {
                "provider": row["triaged_by"],
                "latency_ms": row["triage_latency_ms"],
                "fallback": row["triaged_by"] == "rules:fallback",
            }
            for row in outcomes
        ],
    }
