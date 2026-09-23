"""Direct provider-layer tests for providers/cache.py — real Redis, no
mocks, no HTTP, same precedent as test_repositories.py for the persistence
layer. docs/specs/phase-08-cache-layer.md.
"""

from app.providers import cache
from app.providers.triage.base import Category, Priority, TriageResult


async def _flush_rate_limit(client_ip: str) -> None:
    keys = [key async for key in cache.client.scan_iter(f"ratelimit:{client_ip}:*")]
    if keys:
        await cache.client.delete(*keys)


class TestStatsCache:
    async def test_get_set_delete_round_trip_and_ttl(self) -> None:
        await cache.invalidate_stats_cache()
        assert await cache.get_stats_cache() is None

        data = {
            "counts_by_status": {"open": 1},
            "counts_by_category": {"water": 1},
            "average_triage_latency_ms": 5.0,
        }
        await cache.set_stats_cache(data)
        assert await cache.get_stats_cache() == data

        ttl = await cache.client.ttl(cache._STATS_KEY)
        assert 0 < ttl <= 30

        await cache.invalidate_stats_cache()
        assert await cache.get_stats_cache() is None


class TestRateLimiter:
    _IP = "10.0.0.15"

    async def test_allows_up_to_max_then_blocks_with_positive_retry_after(self) -> None:
        await _flush_rate_limit(self._IP)
        try:
            for _ in range(3):
                allowed, retry_after = await cache.check_rate_limit(
                    self._IP, max_requests=3, window_seconds=60
                )
                assert allowed is True
                assert retry_after == 0

            blocked, retry_after = await cache.check_rate_limit(
                self._IP, max_requests=3, window_seconds=60
            )
            assert blocked is False
            assert retry_after > 0
        finally:
            await _flush_rate_limit(self._IP)


class TestTriageResultCache:
    _TEXT = "A providers/cache.py direct unit test complaint about electricity."
    _LOCATION = "Cache Unit Test Location"

    async def test_get_set_round_trip_and_ttl(self) -> None:
        key = cache._triage_cache_key(self._TEXT, self._LOCATION)
        await cache.client.delete(key)
        try:
            assert await cache.get_triage_cache(self._TEXT, self._LOCATION) is None

            result = TriageResult(
                category=Category.ELECTRICITY,
                priority=Priority.HIGH,
                summary="test",
                confidence=0.9,
                triaged_by="rules",
            )
            payload = result.model_dump(mode="json")
            await cache.set_triage_cache(self._TEXT, self._LOCATION, payload)
            assert await cache.get_triage_cache(self._TEXT, self._LOCATION) == payload

            ttl = await cache.client.ttl(key)
            assert 0 < ttl <= 24 * 60 * 60
        finally:
            await cache.client.delete(key)

    async def test_hit_rate_reflects_this_test_s_own_delta(self) -> None:
        # triage_cache:hits/misses are global cumulative counters shared by
        # the whole suite — assert on the delta this test itself produces,
        # not an absolute value, same precedent as the fallback-counter
        # delta test in test_routes_metrics.py.
        before_hits = int(await cache.client.get(cache._TRIAGE_HITS_KEY) or 0)
        before_misses = int(await cache.client.get(cache._TRIAGE_MISSES_KEY) or 0)

        await cache.record_triage_cache_miss()
        await cache.record_triage_cache_hit()
        await cache.record_triage_cache_hit()

        after_hits = int(await cache.client.get(cache._TRIAGE_HITS_KEY) or 0)
        after_misses = int(await cache.client.get(cache._TRIAGE_MISSES_KEY) or 0)
        assert after_hits - before_hits == 2
        assert after_misses - before_misses == 1

        rate = await cache.triage_cache_hit_rate()
        assert rate == after_hits / (after_hits + after_misses)

    async def test_hit_rate_is_none_when_no_lookups_recorded(self) -> None:
        # Only test allowed to reset the global counters to empty — nothing
        # else in the suite asserts on their absolute value (everything
        # else uses deltas or doesn't read triage_cache_hit_rate() at all),
        # so this is safe regardless of test execution order.
        await cache.client.delete(cache._TRIAGE_HITS_KEY, cache._TRIAGE_MISSES_KEY)
        assert await cache.triage_cache_hit_rate() is None
