"""Session-wide test hygiene — docs/specs/phase-08-cache-layer.md's
As-Built (found during implementation, not anticipated by the Plan).

Phase 8's triage-result cache is keyed by content hash of (text, location).
Several pre-existing tests across the suite reuse the same generic filler
text+location (e.g. "Test Location") to exercise different triage
providers/outcomes. Without a clean slate, a fallback result cached by one
test would silently be replayed for a later test expecting a fresh
(non-fallback) result from a different provider, and vice versa — and
Redis data persists across separate pytest invocations, so a stale key from
a previous run can contaminate the next one too. Flushing the whole test
Redis database once, before any test runs, gives every test a clean cache
regardless of run order or prior-session history.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
async def _flush_redis_once_per_session() -> None:
    from app.providers import cache

    await cache.client.flushdb()
