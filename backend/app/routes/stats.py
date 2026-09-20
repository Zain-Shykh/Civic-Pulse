"""GET /api/stats — docs/CONTRACTS.md §2.2.

Aggregates only this phase — no Redis caching, no X-Cache header. That half
of this contract row is Phase 8's (docs/specs/phase-07-routes.md Non-goals).
"""

from typing import Any

from fastapi import APIRouter

from app.services import complaints as services

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats() -> dict[str, Any]:
    return await services.get_stats()
