"""POST/GET/PATCH /api/complaints... — docs/specs/phase-07-routes.md.

HTTP only: parse, validate, serialise, status codes. Every route here calls
exactly one services/complaints.py function; NotFoundError/
IllegalTransitionError are handled by the global handlers in
app.exception_handlers, not caught here. The one exception is
create_complaint(), which also records the two triage-specific Prometheus
metrics (docs/specs/phase-07b-metrics.md) after calling the service —
observability plumbing, not a business rule, so it stays here rather than
in services/complaints.py (see that spec's Open Question 2).
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.observability import TRIAGE_FALLBACK_TOTAL, TRIAGE_LATENCY_SECONDS
from app.routes.dependencies import TriageProviderDep
from app.schemas.complaints import ComplaintCreateRequest, StatusUpdateRequest
from app.services import complaints as services

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_complaint(
    body: ComplaintCreateRequest, provider: TriageProviderDep
) -> dict[str, Any]:
    created = await services.submit_complaint(
        provider,
        text=body.text,
        location=body.location,
        reporter_contact=body.reporter_contact,
    )
    TRIAGE_LATENCY_SECONDS.observe(created["triage_latency_ms"] / 1000)
    if created["used_fallback"]:
        TRIAGE_FALLBACK_TOTAL.inc()
    return created


@router.get("/{complaint_id}")
async def get_complaint(complaint_id: uuid.UUID) -> dict[str, Any]:
    return await services.get_complaint(complaint_id)


@router.get("")
async def list_complaints(
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    category: str | None = None,
    priority: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    items, total = await services.list_complaints(
        status=status_filter, category=category, priority=priority, page=page, page_size=page_size
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.patch("/{complaint_id}/status")
async def update_status(complaint_id: uuid.UUID, body: StatusUpdateRequest) -> dict[str, Any]:
    return await services.change_status(complaint_id, body.status)
