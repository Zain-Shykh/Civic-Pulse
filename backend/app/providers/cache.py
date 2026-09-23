"""Redis client — a provider concern per docs/architecture/ARCHITECTURE.md
("providers/ Outbound integrations (LLM, cache)").

Only a connection factory and a raw ping today, used by GET /ready. The
stats cache, rate limiter, and triage-result cache built on top of this
client arrive in the Cache Layer phase, with their own spec.
"""

import redis.asyncio as redis

from app.config import settings

client: redis.Redis = redis.from_url(settings.redis_url)


async def ping() -> bool:
    """Raw connectivity check — used only by GET /ready."""
    try:
        return bool(await client.ping())
    except Exception:
        return False
