"""GET /api/meta/providers — docs/CONTRACTS.md §2.2: "Which triage provider
is active, and the last 20 triage outcomes (provider, latency ms, fallback
y/n). This is your observability surface."
"""

from typing import Any

from fastapi import APIRouter

from app.routes.dependencies import TriageProviderDep
from app.services import complaints as services

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/providers")
async def get_providers(provider: TriageProviderDep) -> dict[str, Any]:
    return await services.get_meta_providers(provider)
