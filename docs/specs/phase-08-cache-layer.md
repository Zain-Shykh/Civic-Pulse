# Phase 8: Cache layer
Status: not started
Depends on: Phase 7 (routes must exist to wrap), Phase 7b (carries forward its Open Question 3)
Reads first: docs/CONTRACTS.md §2.4 and §2.5 requirement 5, docs/OPEN-DECISIONS.md #7, docs/specs/phase-07b-metrics.md (Open Question 3), backend/app/providers/cache.py, frontend/nginx.conf

## Goal

Build the three real Redis responsibilities on top of `providers/cache.py`'s
existing connection factory: a read-through cache for `GET /api/stats`
(§2.4 Job 1), a distributed fixed-window rate limiter in front of
`POST /api/complaints` (§2.4 Job 2), and a content-hash triage-result cache
(§2.5 requirement 5) so a repeated complaint costs one Gemini call, not N.
All three are Redis calls behind `providers/cache.py`, invoked from
`services/complaints.py` — the same shape `LLMTriage` already follows for
its own external call — never from `routes/`.

## Scope-gap note (found during research, not silently absorbed)

`docs/IMPLEMENTATION-PLAN.md`'s Phase 8 bullet list names only two
responsibilities: "`/api/stats` read-through caching + invalidation" and
"Redis-backed fixed-window rate limiter." It omits the triage-result cache
entirely. But:

- `docs/CONTRACTS.md` §2.5 requirement 5 requires it explicitly: "Cache by
  content hash in Redis, 24 h TTL — duplicate complaints cost one
  inference, not N. Measured hit rate must be reported."
- `backend/app/providers/triage/llm.py`'s own docstring already says so:
  "Content-hash caching (requirement 5) is explicitly deferred to Phase 8."
- `backend/app/providers/cache.py`'s own docstring already says so too:
  "The stats cache, rate limiter, and triage-result cache built on top of
  this client arrive in the Cache Layer phase."

So three of three sources that actually describe this phase's Redis work
(`CONTRACTS.md`, `llm.py`, `cache.py`) already agree on three
responsibilities — only `IMPLEMENTATION-PLAN.md`'s summary bullet list is
short one. Treated as a stale summary, not a scope decision: all three are
in scope for this spec.

## Deliverables

**(a) Stats read-through cache — `docs/CONTRACTS.md` §2.4 Job 1**

- `providers/cache.py` gains a small get/set/delete surface for a single
  key, `stats:aggregate` (`/api/stats` takes no query params today, so one
  key is the whole cache — confirmed against `routes/stats.py`'s current
  shape).
- `services/complaints.py`'s `get_stats()` checks the cache first; on a
  miss, computes via `repository.stats_summary()` (unchanged) and writes
  the result back with a 30 s TTL. Returns `(data, hit: bool)` rather than
  `data` alone — `routes/stats.py` reads the flag and sets `X-Cache:
  HIT|MISS`, the same "service returns metadata, route turns it into an
  HTTP header" shape Phase 7b's `used_fallback` already established.
- Invalidation: any write that changes what `stats_summary()` aggregates
  (`counts_by_status`, `counts_by_category`, `average_triage_latency_ms`)
  deletes the `stats:aggregate` key. Concretely: `submit_complaint()`
  (changes category counts + average latency) and `change_status()`
  (changes status counts) both invalidate — see Open Questions for
  confirmation this is the full write set.

**(b) Rate limiter — `docs/CONTRACTS.md` §2.4 Job 2**

- Algorithm: fixed-window `INCR` + `EXPIRE`, per `docs/OPEN-DECISIONS.md`
  #7 (already resolved — not relitigated here).
- `providers/cache.py` gains a function that increments a per-IP,
  per-window counter and returns whether the caller is over the limit and,
  if so, the window's remaining TTL (for `Retry-After`).
- Applies to `POST /api/complaints` only — `CONTRACTS.md`'s own Job 2 text
  names exactly that one route ("protecting POST /api/complaints"), no
  others.
- New `RateLimitExceededError` in `services/exceptions.py`, carrying
  `retry_after_seconds`, following the exact existing shape of
  `NotFoundError`/`IllegalTransitionError` (data only, no HTTP knowledge) —
  handled by a new global handler in `exception_handlers.py` returning 429
  + `Retry-After`, registered in `main.py` alongside the other two.
- `services/complaints.py`'s `submit_complaint()` gains a `client_ip: str`
  parameter, checks the limiter before calling the triage provider, and
  raises `RateLimitExceededError` on an exceeded window.
  `routes/complaints.py`'s `create_complaint()` resolves the client IP
  from the request (see Open Question 1) and passes it through — the
  route does IP resolution (an HTTP-layer fact), the service enforces the
  quota rule (a business rule), the provider does the Redis `INCR`
  (infrastructure). No Redis import in `routes/` or in `services/`.

**(c) Triage-result cache — `docs/CONTRACTS.md` §2.5 requirement 5**

- Key: SHA-256 of `text` + `location` together, not `text` alone —
  `TriageProvider.triage(text, location)` takes both as input, so both
  determine the result; hashing `text` only would serve a stale cached
  result for the same complaint text reported at a different location.
- `providers/cache.py` gains get/set for this namespace, 24 h TTL, plus two
  plain Redis counters (`triage_cache:hits`, `triage_cache:misses`, no
  TTL, cumulative) so hit rate is measurable without polluting the public
  complaint response with cache bookkeeping.
- `services/complaints.py`'s `submit_complaint()` checks the cache before
  calling `provider.triage(...)`; a hit skips the provider call entirely
  and increments the hit counter, a miss calls the provider as today,
  caches the result, and increments the miss counter.
- Hit-rate reporting: see Open Question 4 — no new endpoint invented.

## Non-goals

- No change to `/metrics`'s own behavior beyond the exemption decision in
  Open Question 3 (Phase 7b already shipped the endpoint itself).
- No change to the rate-limiter algorithm — fixed-window is already
  decided (`docs/OPEN-DECISIONS.md` #7).
- No token-bucket limiter, no per-user limiting — per-IP only, per
  `CONTRACTS.md`'s literal text.
- No caching of anything other than the three named pieces (no caching
  `GET /api/complaints/{id}` or the list endpoint — not required by
  `CONTRACTS.md` and not asked for).

## Open Questions

**1. Client IP behind the nginx proxy. — RESOLVED 2026-09-22**
Checked `frontend/nginx.conf` directly: it already sets both
`X-Forwarded-For: $proxy_add_x_forwarded_for` and `X-Real-IP:
$remote_addr` on every proxied request to `backend`. So the data is
already there — the question is which one to trust and how.
`$proxy_add_x_forwarded_for` *appends* nginx's own view of the caller to
whatever `X-Forwarded-For` value (if any) the caller already sent — so a
malicious client could pre-set that header to spoof an IP and evade the
per-IP limiter by rotating a claimed value, unless the backend reads the
**last** entry in the list (the one nginx itself appended) rather than the
first (attacker-controlled). Recommendation: read `X-Real-IP` — nginx
sets it from `$remote_addr` directly, so it can't be client-forged — with
a fallback to `request.client.host` only if the header is absent (e.g. a
direct test-client request bypassing nginx entirely, as in the test
suite). Since `backend` publishes no host port (`docs/OPEN-DECISIONS.md`
#11), nginx is the only path a real external request can take today; this
assumption is worth revisiting if Kubernetes (Phase 11) puts a second
proxy hop in front of nginx, but that's not decided here.

**2. What counts as "a write that changes the aggregate" for stats
invalidation. — RESOLVED 2026-09-22**
`stats_summary()`'s three fields (`counts_by_status`,
`counts_by_category`, `average_triage_latency_ms`) are changed by both
complaint creation (category count, average latency) and status changes
(status count) — no other write path exists today. Recommendation:
invalidate on both `submit_complaint()` and `change_status()`. Flagging
for confirmation since it's a completeness claim about "every write that
touches this data," not just a technical detail.

**3. Should `GET /metrics` be exempted from the rate limiter?
(Phase 7b's Open Question 3, inherited here.) — RESOLVED 2026-09-22**
Re-reading `CONTRACTS.md` §2.4 Job 2's literal text: "protecting
**POST /api/complaints**" — the limiter is scoped to that one route by
the contract's own wording, not to the app as a whole. Under Deliverable
(b) above, the limiter is never invoked from any other route, `/metrics`
included. Recommendation: treat this as already resolved by reading the
contract precisely, rather than as a live exemption decision — there is
no rate-limiting anywhere for an exemption to be carved out of. Flagging
for explicit confirmation since this closes out a question carried across
two phases now.

**4. Rate-limit threshold — request count and window length. — DECIDED 2026-09-22: 10 req / 60 s**
`CONTRACTS.md` requires the mechanism (fixed-window, 429 +
`Retry-After`) but names no specific N-requests-per-T-seconds value, and
neither does any other doc read for this spec. Recommendation: 10
requests per 60-second window per IP, configurable via a
`RATE_LIMIT_MAX`/`RATE_LIMIT_WINDOW_SECONDS` env var pair (defaults
10/60) rather than a hardcoded magic number — loosely sized against the
free-tier Gemini quota this limiter exists to protect (~15 RPM total,
`docs/OPEN-DECISIONS.md` #1), leaving headroom for more than one
legitimate citizen submitting at once. This is a genuine value judgment,
not derivable from any doc — needs an explicit decision, not just a
rubber-stamp.

**5. How measured triage-cache hit rate gets surfaced. — RESOLVED 2026-09-22**
`CONTRACTS.md` requires it "reported" but doesn't say where, and no new
endpoint exists in the contract's nine-row table to invent one for.
Recommendation: add a `triage_cache_hit_rate` field (hits / (hits +
misses), `null` if no lookups yet) to `GET /api/meta/providers`'s
existing response — that route is already described in `CONTRACTS.md` as
"your observability surface," and it already reports triage outcomes; a
cache-hit-rate field is a natural extension of the same surface, not a
new one. Flagging explicitly since it extends an already-shipped
endpoint's response shape, the same discipline Phase 7b's Open Question 2
required before touching `routes/complaints.py`.

## Plan

All five Open Questions above are decided (see inline `RESOLVED`/`DECIDED`
tags, 2026-09-22). Implementing exactly against those decisions — no
re-litigation.

### Files touched, in order

Dependency order, not the (a)/(b)/(c) Deliverables grouping — several files
are touched once but serve more than one deliverable, which is why the
order below doesn't map 1:1 onto the lettered list.

1. **`backend/app/config.py`** — add `rate_limit_max: int = 10` and
   `rate_limit_window_seconds: int = 60` to `Settings`, overridable via
   `RATE_LIMIT_MAX`/`RATE_LIMIT_WINDOW_SECONDS` env vars (pydantic-settings
   reads the field name upper-cased automatically, matching
   `database_url`/`redis_url`/`gemini_api_key`'s existing pattern — no new
   config mechanism introduced). Touched first: everything downstream that
   reads these defaults needs the field to exist.

2. **`backend/app/providers/cache.py`** — the one file every deliverable
   depends on. Touched second, before anything that calls it. Full new
   surface (exact signatures below), plus one change to the existing
   `client` construction line: `redis.from_url(settings.redis_url,
   decode_responses=True)` — checked directly, the current line has no
   `decode_responses`, so `client.get(...)` returns `bytes` today; every
   new function below assumes `str` back from Redis, so this one-line
   change is a prerequisite, not an incidental drive-by edit.

3. **`backend/app/services/exceptions.py`** — add `RateLimitExceededError`,
   matching `NotFoundError`/`IllegalTransitionError`'s exact existing shape
   (constructor stores the data a handler needs, calls `super().__init__`
   with a message, no HTTP knowledge). Touched third: `exception_handlers.py`
   and `services/complaints.py` both need the class to exist first.

4. **`backend/app/exception_handlers.py`** — add
   `rate_limit_exceeded_handler`, same shape as the two existing handlers
   (`assert isinstance(exc, RateLimitExceededError)`, build a `JSONResponse`
   with `status_code=429` and a `Retry-After` header). Touched fourth, right
   after the exception it maps.

5. **`backend/app/services/complaints.py`** — the business-logic wiring for
   all three deliverables in one file:
   - `get_stats()` — cache-aside read, returns `(data, hit: bool)`.
   - `change_status()` — invalidates `stats:aggregate` after a successful
     status write.
   - `submit_complaint()` — gains a `client_ip: str` keyword parameter;
     checks the rate limiter first (raises `RateLimitExceededError` before
     touching the triage provider or the repository at all); then checks
     the triage-result cache before calling `provider.triage(...)`; then
     invalidates `stats:aggregate` after a successful create (same as
     today's create path, now also touching the cache).
   - `get_meta_providers()` — adds `triage_cache_hit_rate` to its returned
     dict.
   Touched fifth: needs `cache.py` (step 2) and the new exception (step 3)
   to exist first.

6. **`backend/app/routes/complaints.py`** — `create_complaint()` resolves
   the client IP (`request.headers.get("x-real-ip") or request.client.host
   if request.client else "unknown"`) and passes it to
   `services.submit_complaint(..., client_ip=...)`. No other change to this
   route; the existing metrics-recording lines (Phase 7b) are unaffected —
   `RateLimitExceededError` is raised inside the service call, before
   `create_complaint()`'s own metrics lines ever run, and is caught by the
   global handler (step 4), not by this route. Touched sixth: needs
   `submit_complaint()`'s new signature (step 5) to exist first.

7. **`backend/app/routes/stats.py`** — `get_stats()` unpacks
   `(data, hit)` from the service call and returns a `Response` with the
   `X-Cache` header set (`"HIT"` if `hit` else `"MISS"`) — same shape as
   any other FastAPI route that needs to set a header, no new pattern.
   Touched seventh: needs `services.get_stats()`'s new return shape (step 5).

8. **`backend/app/main.py`** — register
   `app.add_exception_handler(RateLimitExceededError,
   rate_limit_exceeded_handler)` alongside the other two. Touched last:
   needs the handler (step 4) to exist.

**Test files** (mechanical updates and new scenarios — see Verification
required below for the scenarios themselves):

9. `backend/tests/test_services_complaints.py` — existing direct calls to
   `submit_complaint()` (three call sites, per the Phase 7b As-Built)
   updated to pass `client_ip="10.0.0.1"` (or similar fixed test IP) —
   mechanical, required by step 5's new parameter, not a new test
   scenario. Plus one new test (triage-cache call-counting).
10. `backend/tests/test_routes_complaints.py` — existing `client` fixture
    given a fixed `X-Real-IP` default (see "Test isolation for the rate
    limiter" below); one new test class for the 429 scenario.
11. `backend/tests/test_routes_stats.py` — new file.
12. `backend/tests/test_providers_cache.py` — new file.

### `providers/cache.py` — exact new signatures

```python
import hashlib
import json
import time
from typing import Any

# --- stats cache (Deliverable a) ---
_STATS_KEY = "stats:aggregate"
_STATS_TTL_SECONDS = 30

async def get_stats_cache() -> dict[str, Any] | None: ...
async def set_stats_cache(data: dict[str, Any]) -> None: ...
async def invalidate_stats_cache() -> None: ...

# --- rate limiter (Deliverable b) ---
async def check_rate_limit(
    client_ip: str, *, max_requests: int, window_seconds: int
) -> tuple[bool, int]:
    """Fixed-window INCR+EXPIRE, keyed by client_ip and the current window
    bucket (`int(time.time()) // window_seconds`). Returns
    (allowed, retry_after_seconds) — retry_after_seconds is the window
    key's remaining TTL when not allowed, 0 when allowed."""
    ...

# --- triage-result cache (Deliverable c) ---
_TRIAGE_TTL_SECONDS = 24 * 60 * 60

def _triage_cache_key(text: str, location: str) -> str:
    """SHA-256 of text+location together (both inputs to
    TriageProvider.triage(), per Deliverable c's key-composition note)."""
    ...

async def get_triage_cache(text: str, location: str) -> dict[str, Any] | None: ...
async def set_triage_cache(text: str, location: str, result: dict[str, Any]) -> None: ...
async def record_triage_cache_hit() -> None: ...
async def record_triage_cache_miss() -> None: ...
async def triage_cache_hit_rate() -> float | None:
    """hits / (hits + misses); None if no lookups have happened yet."""
    ...
```

`get_stats_cache`/`get_triage_cache` store/load via `json.dumps`/
`json.loads` against plain `dict`s — `set_triage_cache` is given
`result.model_dump(mode="json")` (a `TriageResult`'s enum fields become
plain strings), and a hit is reconstructed via
`TriageResult.model_validate(cached)` in `services/complaints.py` so the
rest of `submit_complaint()` treats a cache hit identically to a fresh
provider call or a fallback — one `TriageResult` variable regardless of
which of the three paths produced it, matching the existing fallback
branch's own shape.

**On a cache hit,** `triage_latency_ms` is still measured as this
request's own elapsed time around the triage step (the cache lookup, not
the original provider call) — the metric's meaning stays "time this
request spent in the triage step," whichever path it took, consistent
with how `TRIAGE_LATENCY_SECONDS` is already documented in
`observability.py`. `triaged_by` is preserved verbatim from the cached
result (e.g. still `"llm:gemini"`) — a cache hit changes *cost*, not
*attribution*; `used_fallback`'s existing derivation
(`triaged_by == "rules:fallback"`) needs no change.

### Test isolation for the rate limiter

Every test that POSTs to `/api/complaints` through a shared `TestClient`
now shares one `request.client.host` (`"testclient"`, Starlette's TestClient
default) unless something overrides it — meaning, un-addressed, every
existing HTTP-level create test across `test_routes_complaints.py` and
`test_routes_metrics.py` would silently share one 10-req/60s bucket with
the new rate-limit test, causing spurious 429s in unrelated tests the
moment the suite's cumulative POST count crosses 10 within a minute. This
is a real correctness risk this Plan has to close, not an incidental
detail:

- `test_routes_complaints.py`'s existing `client` fixture gains a fixed
  `headers={"X-Real-IP": "10.0.0.1"}` default (httpx's `TestClient`
  supports default headers at construction) — every existing test in that
  file now resolves to the same fixed, harmless IP, distinct from the
  rate-limit test's own IP below.
- `test_routes_metrics.py`'s `client` fixture gets its own distinct fixed
  IP (`10.0.0.2`) for the same reason — it also POSTs to
  `/api/complaints`.
- The new rate-limit test in `test_routes_complaints.py` uses a third,
  dedicated IP (`10.0.0.3`) local to that test only, and explicitly
  deletes any `ratelimit:10.0.0.3:*` keys via a direct `cache.client.keys()`
  + `delete()` call in a `finally` block, so a re-run of the suite within
  the same 60 s window doesn't inherit a stale count.

### Four-layer rule — confirmed per deliverable, not just asserted

- **(a) Stats cache:** `redis`/`cache` is imported only in
  `providers/cache.py`. `services/complaints.py` imports
  `app.providers.cache` functions, never `redis` directly.
  `routes/stats.py` imports neither — it reads a `(dict, bool)` tuple back
  from the service call and sets a plain HTTP header from the `bool`.
- **(b) Rate limiter:** same import boundary. `routes/complaints.py` adds
  no cache/Redis import at all — it extracts a plain `str` (the IP) from
  `Request` (already an HTTP-layer object it already has access to) and
  passes it as a string parameter to a service function, exactly like it
  already passes `body.text`/`body.location`. The Redis `INCR` happens
  only inside `providers/cache.py`, called from `services/complaints.py`.
- **(c) Triage cache:** identical boundary — `routes/complaints.py` is
  entirely unaware the cache exists; `submit_complaint()`'s public
  contract (parameters in, dict out) is unchanged by adding the cache
  check internally.

### Still uncertain (not manufactured certainty)

- **redis-py's exact `TTL` return values on edge cases** (key expired
  mid-check, key exists with no TTL) — `check_rate_limit`'s `retry_after`
  needs `max(ttl, 0)` defensively, but the precise `-1`/`-2` semantics
  should be confirmed empirically against the real `redis:7-alpine`
  instance during implementation, not assumed from memory of the redis-py
  API.
- **Fixed-window boundary bursts** (a client landing requests just before
  and just after a window boundary can briefly exceed the nominal rate) —
  this is an accepted, known property of the fixed-window algorithm itself
  (`docs/OPEN-DECISIONS.md` #7 already chose it over token-bucket for
  simplicity, accepting this trade-off), not a new gap introduced here.
- **Whether 10 req/60s is comfortable for the full test suite's own
  traffic** — addressed via the fixed test IPs above, but if a future test
  file adds more HTTP-level complaint-creation tests without adopting the
  same fixed-IP convention, it could reintroduce the collision risk this
  Plan just closed. Worth a one-line comment at each fixture, not a
  structural guarantee.

## Verification required

- `ruff check .` and `mypy app` — verbatim output, both clean (restating
  project convention, not a new requirement).
- Full `pytest` run — verbatim tail, real pass count.
- **`backend/tests/test_providers_cache.py` (new):** direct exercises of
  `providers/cache.py` against real Redis (no HTTP, no mocks, matching
  `test_repositories.py`'s precedent for direct provider/repository-level
  tests): stats get/set/delete round-trip and TTL; `check_rate_limit`
  under the threshold (allowed) and at/over it (blocked, `retry_after > 0`);
  triage-cache get/set round-trip; hit/miss counters and
  `triage_cache_hit_rate`'s arithmetic, including the `None`-when-empty
  case.
- **`backend/tests/test_routes_complaints.py` (extended):** new
  `TestRateLimiting` class — drive `RATE_LIMIT_MAX` (10) requests from the
  dedicated test IP, assert all succeed, then assert the next one returns
  `429` with a `Retry-After` header present and numeric. Cleans up every
  created row and the Redis key(s) it used, per the isolation section
  above.
- **`backend/tests/test_routes_stats.py` (new):** `GET /api/stats`
  sequencing test — invalidate/clear the cache first, assert the first
  call is `X-Cache: MISS`, assert the immediately-following call is
  `X-Cache: HIT` with identical data, then `POST /api/complaints`, then
  assert the very next `GET /api/stats` is `X-Cache: MISS` again *and* its
  data reflects the new complaint (proves invalidation-on-write, not just
  eventual TTL expiry — the spec's explicit requirement).
- **`backend/tests/test_services_complaints.py` (extended):** the three
  existing `submit_complaint()` call sites updated for the new
  `client_ip` parameter (no behavior change, confirm they still pass);
  one new test wrapping `SimulatedTriage` in a call-counting spy, POSTing
  (calling `submit_complaint()` directly) the same `text`+`location` twice,
  asserting the spy's `triage()` was invoked exactly once and both results
  carry identical category/priority/summary/`triaged_by`.

## Ambiguity handling
Open Questions 1–5 above are the ambiguities found; none silently
resolved. Everything else in `CONTRACTS.md` §2.4/§2.5 requirement 5 read
as unambiguous given the codebase state checked.

## As-Built
(not started)
