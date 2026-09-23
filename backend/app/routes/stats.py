"""GET /api/stats — docs/CONTRACTS.md §2.2, §2.4 Job 1.

Redis read-through cache, 30s TTL, X-Cache: HIT|MISS — docs/specs/
phase-08-cache-layer.md, Deliverable (a). services.get_stats() does the
caching itself and returns (data, hit); this route only turns `hit` into
the HTTP header, per the four-layer rule.
"""

from typing import Any

from fastapi import APIRouter, Response

from app.services import complaints as services

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats(response: Response) -> dict[str, Any]:
    data, hit = await services.get_stats()
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return data
