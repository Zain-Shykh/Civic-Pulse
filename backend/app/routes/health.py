"""GET /health and GET /ready — the walking-skeleton routes for this phase.

/ready calls app.db.ping / app.providers.cache.ping directly, bypassing
services/ and repositories/. This is a deliberate, scoped exception to the
four-layer rule in CLAUDE.md — see docs/adr/0005-ready-endpoint-layering-
exception.md for the full justification and scope. It applies ONLY to these
two routes and ONLY to raw reachability checks; no other route gets this
exception.
"""

from fastapi import APIRouter, Response, status

from app.db import ping as db_ping
from app.providers.cache import ping as redis_ping

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness. Process is alive. Must not touch the database (§2.2)."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    """Readiness. 200 only if Postgres and Redis are both reachable;
    503 naming the failed dependency (§2.2).
    """
    postgres_ok = await db_ping()
    redis_ok = await redis_ping()

    if postgres_ok and redis_ok:
        return {"status": "ready"}

    failed = [name for name, ok in (("postgres", postgres_ok), ("redis", redis_ok)) if not ok]
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not_ready", "failed_dependencies": failed}
