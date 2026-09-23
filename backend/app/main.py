"""CivicPulse backend entrypoint.

Phase 7: the full API contract is wired up. The TriageProvider is
constructed once here, at startup, and stored on app.state (docs/specs/
phase-07-routes.md, Open Question 4) — routes/dependencies.py reads the
same instance back on every request. Phase 7b adds GET /metrics via
prometheus-fastapi-instrumentator. Phase 8 adds the stats cache, rate
limiter, and triage-result cache (docs/specs/phase-08-cache-layer.md).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from prometheus_fastapi_instrumentator import Instrumentator

from app.exception_handlers import (
    illegal_transition_handler,
    not_found_handler,
    rate_limit_exceeded_handler,
    validation_error_handler,
)
from app.providers.triage.factory import get_triage_provider
from app.routes.complaints import router as complaints_router
from app.routes.health import router as health_router
from app.routes.meta import router as meta_router
from app.routes.stats import router as stats_router
from app.services.exceptions import IllegalTransitionError, NotFoundError, RateLimitExceededError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.triage_provider = get_triage_provider()
    yield


app = FastAPI(title="CivicPulse", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)

app.include_router(health_router)
app.include_router(complaints_router)
app.include_router(meta_router)
app.include_router(stats_router)

app.add_exception_handler(NotFoundError, not_found_handler)
app.add_exception_handler(IllegalTransitionError, illegal_transition_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(RateLimitExceededError, rate_limit_exceeded_handler)
