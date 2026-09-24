"""Redis client — a provider concern per docs/architecture/ARCHITECTURE.md
("providers/ Outbound integrations (LLM, cache)").

Three responsibilities, all called from services/complaints.py only, never
from routes/ — docs/specs/phase-08-cache-layer.md's Plan:

- Stats read-through cache (Deliverable a, CONTRACTS.md §2.4 Job 1).
- Fixed-window rate limiter (Deliverable b, CONTRACTS.md §2.4 Job 2).
- Triage-result content-hash cache (Deliverable c, CONTRACTS.md §2.5 req 5).

Plus the original raw ping, used only by GET /ready.
"""

import asyncio
import hashlib
import json
import time
import weakref
from typing import Any

import redis.asyncio as redis

from app.config import settings


def _connect() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


# One Redis client per running event loop, not one global client. Production
# has exactly one event loop for the app's whole life, so this is
# functionally a singleton there. Tests are the reason this exists: each
# `TestClient(app)` instance runs the ASGI app in its own anyio portal
# thread/loop, while a test's own body (direct cache.* calls, not through
# HTTP) runs on pytest's own loop — two different, simultaneously-alive
# loops in the same test, each needing its own connection to the same
# physical Redis server. A single shared async client breaks the moment a
# second loop touches it (asyncio transports can't cross loops). Found and
# fixed during Phase 8 implementation — docs/specs/phase-08-cache-layer.md's
# As-Built. A WeakKeyDictionary means an entry is dropped automatically once
# its loop (e.g. a finished portal thread's loop) is garbage collected.
_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, redis.Redis]" = (
    weakref.WeakKeyDictionary()
)


def _client_for_current_loop() -> redis.Redis:
    loop = asyncio.get_running_loop()
    existing = _clients.get(loop)
    if existing is None:
        existing = _connect()
        _clients[loop] = existing
    return existing


def __getattr__(name: str) -> Any:
    """Lets `cache.client` keep working as a plain attribute (used directly
    by several tests) while actually resolving to the current loop's client
    (PEP 562)."""
    if name == "client":
        return _client_for_current_loop()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def ping() -> bool:
    """Raw connectivity check — used only by GET /ready."""
    try:
        return bool(await _client_for_current_loop().ping())
    except Exception:
        return False


# --- stats cache (Deliverable a) ---

_STATS_KEY = "stats:aggregate"
_STATS_TTL_SECONDS = 30


async def get_stats_cache() -> dict[str, Any] | None:
    raw = await _client_for_current_loop().get(_STATS_KEY)
    return json.loads(raw) if raw is not None else None


async def set_stats_cache(data: dict[str, Any]) -> None:
    await _client_for_current_loop().set(_STATS_KEY, json.dumps(data), ex=_STATS_TTL_SECONDS)


async def invalidate_stats_cache() -> None:
    await _client_for_current_loop().delete(_STATS_KEY)


# --- rate limiter (Deliverable b) ---


async def check_rate_limit(
    client_ip: str, *, max_requests: int, window_seconds: int
) -> tuple[bool, int]:
    """Fixed-window INCR+EXPIRE, keyed by client_ip and the current window
    bucket (`docs/OPEN-DECISIONS.md` #7). Returns (allowed,
    retry_after_seconds) — retry_after_seconds is the window key's
    remaining TTL when not allowed, 0 when allowed."""
    client = _client_for_current_loop()
    bucket = int(time.time()) // window_seconds
    key = f"ratelimit:{client_ip}:{bucket}"
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window_seconds)
    if count > max_requests:
        ttl = await client.ttl(key)
        return False, max(ttl, 0)
    return True, 0


# --- triage-result cache (Deliverable c) ---

_TRIAGE_TTL_SECONDS = 24 * 60 * 60
_TRIAGE_HITS_KEY = "triage_cache:hits"
_TRIAGE_MISSES_KEY = "triage_cache:misses"


def _triage_cache_key(text: str, location: str) -> str:
    """SHA-256 of text+location together — both are inputs to
    TriageProvider.triage(), so both determine the result (Deliverable c's
    key-composition note)."""
    digest = hashlib.sha256(f"{text}\0{location}".encode()).hexdigest()
    return f"triage:{digest}"


async def get_triage_cache(text: str, location: str) -> dict[str, Any] | None:
    raw = await _client_for_current_loop().get(_triage_cache_key(text, location))
    return json.loads(raw) if raw is not None else None


async def set_triage_cache(text: str, location: str, result: dict[str, Any]) -> None:
    await _client_for_current_loop().set(
        _triage_cache_key(text, location), json.dumps(result), ex=_TRIAGE_TTL_SECONDS
    )


async def record_triage_cache_hit() -> None:
    await _client_for_current_loop().incr(_TRIAGE_HITS_KEY)


async def record_triage_cache_miss() -> None:
    await _client_for_current_loop().incr(_TRIAGE_MISSES_KEY)


async def triage_cache_hit_rate() -> float | None:
    """hits / (hits + misses); None if no lookups have happened yet."""
    client = _client_for_current_loop()
    hits = int(await client.get(_TRIAGE_HITS_KEY) or 0)
    misses = int(await client.get(_TRIAGE_MISSES_KEY) or 0)
    total = hits + misses
    return (hits / total) if total else None
