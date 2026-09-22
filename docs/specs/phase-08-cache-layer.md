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

**1. Client IP behind the nginx proxy.**
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
invalidation.**
`stats_summary()`'s three fields (`counts_by_status`,
`counts_by_category`, `average_triage_latency_ms`) are changed by both
complaint creation (category count, average latency) and status changes
(status count) — no other write path exists today. Recommendation:
invalidate on both `submit_complaint()` and `change_status()`. Flagging
for confirmation since it's a completeness claim about "every write that
touches this data," not just a technical detail.

**3. Should `GET /metrics` be exempted from the rate limiter?
(Phase 7b's Open Question 3, inherited here.)**
Re-reading `CONTRACTS.md` §2.4 Job 2's literal text: "protecting
**POST /api/complaints**" — the limiter is scoped to that one route by
the contract's own wording, not to the app as a whole. Under Deliverable
(b) above, the limiter is never invoked from any other route, `/metrics`
included. Recommendation: treat this as already resolved by reading the
contract precisely, rather than as a live exemption decision — there is
no rate-limiting anywhere for an exemption to be carved out of. Flagging
for explicit confirmation since this closes out a question carried across
two phases now.

**4. Rate-limit threshold — request count and window length.**
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

**5. How measured triage-cache hit rate gets surfaced.**
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
(pending approval — not filled in yet)

## Verification required
(to be finalized once the Plan above is approved; the shape it will take)

- A rate-limit test that actually drives requests past the configured
  threshold and asserts a real `429` with a `Retry-After` header present
  and numeric.
- A stats-cache test that proves invalidation-on-write specifically: seed
  a long TTL, write a complaint, and assert the very next `GET /api/stats`
  reflects it (not stale-until-expiry) with `X-Cache: MISS` on that
  recompute and `X-Cache: HIT` on the read immediately after.
- A triage-cache test using a call-counting wrapper around
  `SimulatedTriage` (not a real Gemini call — CI determinism, no network):
  submit the same `text`+`location` twice, assert the wrapped provider's
  `triage()` was invoked exactly once, and that both responses carry the
  same category/priority/summary.

## Ambiguity handling
Open Questions 1–5 above are the ambiguities found; none silently
resolved. Everything else in `CONTRACTS.md` §2.4/§2.5 requirement 5 read
as unambiguous given the codebase state checked.

## As-Built
(not started)
