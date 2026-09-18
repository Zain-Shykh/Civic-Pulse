"""SQLAlchemy async engine setup.

This is infrastructure (engine/session configuration), not a repository —
repositories/ (arriving in the Data Layer phase) will hold the actual
domain queries built on top of the sessions this module produces. The only
thing this module is used for today is the /ready liveness-of-dependency
check, which needs a raw connectivity probe, not a domain query.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import settings

engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)


async def ping() -> bool:
    """Raw connectivity check — used only by GET /ready. Not a repository method."""
    try:
        async with engine.connect():
            return True
    except Exception:
        return False
