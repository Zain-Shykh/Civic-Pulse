# Phase 7b: Observability middleware
Status: done
Depends on: Phase 7 (routes)
Reads first: docs/CONTRACTS.md §2.2 (the /metrics row), docs/RUBRIC-CHECKLIST.md (Bonus section), docs/architecture/ARCHITECTURE.md (network design), backend/app/services/complaints.py (existing logging precedent), backend/app/main.py (router/middleware house style)

## Goal
Expose a `GET /metrics` endpoint in Prometheus text format carrying exactly the
four metrics CONTRACTS.md §2.2 names: request count, request latency
histogram, triage latency, and a fallback counter — the generic pair via
cross-cutting ASGI middleware, the triage-specific pair via a hook next to
the only place in the codebase where triage outcome and timing coexist,
`submit_complaint()`.

## Deliverables
> **Corrected 2026-09-22**, as part of filling in `## Plan` below: the two
> bullets in this section describing the `/metrics` route file and the
> triage-hook location were written before Open Questions 1-2 were decided
> and are now stale. Rewritten to match the actual decisions (see `## Plan`
> for the reasoning behind both corrections).

- `GET /metrics`, exposed via `Instrumentator().expose(app)` directly in
  `main.py` — **no separate `backend/app/routes/metrics.py` file** (the
  originally-drafted Deliverables text named one; superseded once Plan
  research showed `.expose(app)` self-registers the endpoint against the
  same default Prometheus registry the hand-declared custom metrics also
  use — see Plan, "Why no `routes/metrics.py`").
- Generic instrumentation covering every request automatically:
  - **request count** — CONTRACTS.md §2.2: "request count"
  - **request latency histogram** — CONTRACTS.md §2.2: "request latency histogram"

  Cross-cutting, via `prometheus-fastapi-instrumentator`'s
  `Instrumentator().instrument(app).expose(app)`, registered in `main.py`.
- Triage-specific instrumentation:
  - **triage latency** — CONTRACTS.md §2.2: "triage latency"
  - **fallback counter** — CONTRACTS.md §2.2: "fallback counter"

  **Corrected per OQ2's decision:** NOT recorded inside
  `services/complaints.py` (the originally-drafted text proposed this and
  is superseded). `services/complaints.py` stays free of any Prometheus
  import. `submit_complaint()`'s existing return value gains one new field,
  `used_fallback: bool` (derived from `result.triaged_by == "rules:fallback"`,
  the same check `get_meta_providers()` already makes at line 112) — no new
  timing plumbing, since `triage_latency_ms` is already computed and
  returned. `routes/complaints.py`'s `create_complaint()`, after calling
  `services.submit_complaint()`, reads `triage_latency_ms` and
  `used_fallback` off the result and records both Prometheus metrics itself.

  Exactly these four metrics — no fifth metric invented, none of the four dropped.
- New file `backend/app/observability.py`: declares the two hand-built
  Prometheus objects (a `Histogram` for triage latency, a `Counter` for
  fallback count) on the default registry, importable by `routes/complaints.py`.
- Wiring in `backend/app/main.py`: `Instrumentator().instrument(app).expose(app)`
  call (first use of this library in the app) alongside the existing
  flat-list router/handler registration style.

## Non-goals
- No Prometheus server, no scrape config, no Grafana dashboard, no committed
  screenshot. RUBRIC-CHECKLIST.md's full +2 bonus line — "Prometheus scraping
  /metrics plus a Grafana dashboard, screenshot committed" — requires all
  three; this phase only builds the `/metrics` endpoint and the
  instrumentation behind it. Whether/when the scraping Prometheus instance
  and Grafana dashboard get built is a separate, not-yet-scoped decision.
- No rate limiting on `/metrics` (Phase 8 owns rate limiting generally;
  whether `/metrics` is exempted is Open Question 3, for Phase 8's spec to
  inherit, not decided here).
- No caching of `/metrics` (Phase 8's cache layer is for `/api/stats`; a
  metrics endpoint must never be cached).
- No changes to `/health`/`/ready` (ADR 0005's scope is unaffected).
- No access restriction (auth, network placement) decided — Open Question 4.

## Open Questions
1. **Library choice — RESOLVED, approved 2026-09-22.** No metrics library
   was pinned in `backend/pyproject.toml`. Decision: add
   `prometheus-fastapi-instrumentator` as the one new dependency, exactly as
   proposed (wraps `prometheus_client`, no second new dependency needed).
2. **Where the triage-specific hook lives — RESOLVED, decided 2026-09-22,
   NOT the proposed option.** The original proposal (directly inside
   `submit_complaint()` in `services/complaints.py`, on the logging
   precedent) was rejected. Decision instead: `services/complaints.py`
   stays free of any Prometheus import — `submit_complaint()` only gains a
   `used_fallback: bool` field on its return value. The route layer
   (`routes/complaints.py`), after calling the service, reads
   `triage_latency_ms` and `used_fallback` and records both Prometheus
   metrics itself. See Deliverables and Plan for the resulting file changes.
3. **Rate-limit exemption for `/metrics`.** Not decided here — flagged so
   Phase 8's spec addresses it explicitly (a scraper polling every 15s
   should probably never be rate-limited, but that's Phase 8's call).
4. **Access restriction / network placement.** Checked `docs/architecture/ARCHITECTURE.md`
   directly: it says nothing about `/metrics` specifically, and more
   concretely — `compose.yaml`'s `backend` service publishes no host port at
   all today (only `frontend` has `ports: ["8080:8080"]`). A real, host-run
   Prometheus instance cannot scrape `/metrics` under the current compose
   shape without either publishing a backend port or running Prometheus
   itself as a compose service on the `edge` network. Genuinely undecided;
   not deciding it here, just surfacing it since it blocks the bonus item's
   later phases.

## Plan

**Files touched, in order:**

1. `backend/pyproject.toml` — add `prometheus-fastapi-instrumentator` to
   `dependencies` (pinned, per this project's version-pinning convention).
2. `backend/app/observability.py` (new) — module-level, default-registry
   Prometheus objects:
   - `TRIAGE_LATENCY_SECONDS = Histogram("triage_latency_seconds", ...)`
   - `TRIAGE_FALLBACK_TOTAL = Counter("triage_fallback_total", ...)`

   Seconds, not milliseconds, per Prometheus's own naming convention (base
   units in metric names) — `triage_latency_ms` (the DB column / dict key)
   converts to seconds at the point of observation. This is a small,
   low-stakes naming choice, not an Open Question.
3. `backend/app/services/complaints.py` — `submit_complaint()`'s final
   `return await repository.create(...)` becomes: capture the created row,
   then return `{**row, "used_fallback": result.triaged_by == "rules:fallback"}`.
   `result` is the existing `TriageResult` local (real or the
   fallback-constructed one) — no new variable needed, this check is
   identical to `get_meta_providers()`'s existing one on the same field.
4. `backend/app/routes/complaints.py` — `create_complaint()` changes from
   a direct passthrough to: call `services.submit_complaint(...)`, capture
   the result, call `.observe()`/`.inc()` on the two `observability.py`
   metrics using `result["triage_latency_ms"]` and `result["used_fallback"]`,
   then return `result` unchanged (same response body as before — the two
   new fields already existed in the returned dict from Phase 7 onward
   except `used_fallback`, which is additive, not a breaking change to
   the documented 201 response).
5. `backend/app/main.py` — import `Instrumentator` from
   `prometheus_fastapi_instrumentator`; add
   `Instrumentator().instrument(app).expose(app)` once, after
   `app = FastAPI(...)` and before the `add_exception_handler` calls
   (ordering doesn't matter functionally, but keeps app-construction,
   then instrumentation, then routers, then handlers — mirrors the file's
   existing top-to-bottom grouping by concern).

**Why no `routes/metrics.py`:** the originally-drafted Deliverables named
this file. Researching OQ1's `Instrumentator().expose(app)` call showed it
self-registers `GET /metrics` on the app directly, reading whatever is on
the default Prometheus registry at request time — which includes the
hand-declared `observability.py` metrics automatically, since those are
also declared against the default registry (no custom `CollectorRegistry`
passed anywhere). A hand-written route wrapping `generate_latest()` would
be strictly redundant code duplicating what the library already does.
Dropping the file is a Plan-time simplification, disclosed here rather than
carried out silently — flag if a dedicated route file is wanted anyway
(e.g. for later hand-adding response headers `.expose()` doesn't support).

**Key technical choices:**
- **Metric recording lives in the route, not the service** (OQ2's
  decision) — `services/complaints.py` never imports `prometheus_client`,
  keeping the four-layer boundary clean on this axis; the cost is
  `routes/complaints.py` now reads two fields (`triage_latency_ms`,
  `used_fallback`) out of the service's return dict purely to hand them to
  Prometheus, which is HTTP/observability plumbing, arguably legitimate
  route-layer work rather than a business rule.
- **`used_fallback` is additive to the POST /api/complaints response body.**
  CONTRACTS.md doesn't enumerate the full 201 response shape, and
  `triaged_by`/`triage_latency_ms` already leak into it today (via
  `repository.create()`'s `RETURNING *`); adding one more derived boolean
  field is consistent with what's already exposed, not a new category of
  leak. Not proposing to strip fields from the response — out of scope,
  not asked for.
- **`prometheus-fastapi-instrumentator`'s default registry is process-global**,
  which matters directly for how Verification below has to assert on
  counter values (see below).

**Still uncertain / carried forward, not decided in this Plan:**
- OQ3 (rate-limit exemption for `/metrics`) — stays with Phase 8.
- OQ4 (Prometheus can't reach `/metrics` under the current compose shape,
  since `backend` publishes no host port) — stays out of scope here, not
  re-decided, not dropped; still blocks the rest of the bonus item.

## Verification required

- `cd backend && ruff check . && mypy app` — clean, no new violations.
- `cd backend && pytest` — full suite green, no regressions in the existing
  153 tests.
- **New HTTP-level test, `TestMetricsEndpoint` in `test_routes_complaints.py`
  or a new `test_routes_metrics.py`** (file choice at implementation time,
  not a Plan-level decision): with `TestClient(app)` as a context manager,
  `GET /metrics` returns 200 with a Prometheus-text `Content-Type` and the
  body contains all four metric family names (`http_request` count/latency
  families from the instrumentator, `triage_latency_seconds`,
  `triage_fallback_total`).
- **Mandatory fallback-counter test, same mechanism as Phase 7's
  Determinism test:** `app.dependency_overrides[get_triage_provider] =
  lambda: SimulatedTriage(always_raise=True)`, then `POST /api/complaints`
  (asserts 201, unchanged from the existing Determinism test), then
  `GET /metrics` **twice — once before, once after** the POST — and assert
  the *delta* in `triage_fallback_total`'s value is exactly +1, not that
  the raw value equals a fixed number. This is required because
  `prometheus_client`'s default registry is process-global and cumulative
  across the whole test session — asserting an absolute value would be
  order-dependent and flaky the moment another test in the same run also
  exercises the fallback path.
- **Separate services-layer unit test (not HTTP), asserting `used_fallback`
  directly:** call `services.submit_complaint()` once with a provider that
  raises and once with one that doesn't (no HTTP, no metrics assertion —
  this is the field's own correctness, independent of whether the route
  records it into Prometheus correctly). Two assertions:
  `result["used_fallback"] is True` / `is False` respectively. This is a
  distinct test from the metrics-delta test above, per the question this
  round raised explicitly — the field's presence/correctness on the
  service's return value is verified separately from the route recording
  it into Prometheus.
- Manual: `docker compose up -d --build backend`, then from a container on
  the same network, `curl` (or `httpx`) `GET /metrics`, paste real output
  confirming Prometheus text format and all four metric families present.

## Ambiguity handling
If anything here conflicts with CONTRACTS.md or is underspecified, stop and
ask — do not silently resolve.

## As-Built

Implemented exactly against the approved Plan (commit `8c55481`) — the
five-file list (`pyproject.toml`, `observability.py`, `services/complaints.py`,
`routes/complaints.py`, `main.py`), plus the two new test files the Plan
already anticipated as an implementation-time detail (`test_routes_metrics.py`
new file; `test_services_complaints.py` extended with `used_fallback`
assertions on its existing tests, no new test functions needed there).
`routes/complaints.py`'s module docstring updated per this round's rider,
disclosing that `create_complaint()` also records two Prometheus metrics.

### Deviation 1 — dependency version, disclosed

The Plan specified `prometheus-fastapi-instrumentator==7.1.0`. Installing
it forced `starlette` from `1.6.0` (fastapi `0.141.1`'s own preferred
version) down to `0.52.1` (`7.1.0` pins `starlette<1.0.0,>=0.30.0`). Every
real request then crashed inside the instrumentator's own middleware:

```
AttributeError: '_IncludedRouter' object has no attribute 'path'
  File ".../prometheus_fastapi_instrumentator/routing.py", line 55, in _get_route_name
    route_name = route.path
```

Root cause, confirmed by reading both libraries' source directly: FastAPI
(>= 0.116) wraps routers registered via `include_router()` in an internal
`_IncludedRouter` object with no `.path` attribute; `7.1.0`'s hand-rolled
route-name resolver (written against an older Starlette/FastAPI route
model) doesn't know about it and crashes on every single request, not just
`/metrics` — this would have broken every endpoint in production.
`prometheus-fastapi-instrumentator==8.1.0`'s own `routing.py` explicitly
documents and fixes exactly this case (`_effective_routes()`, comment:
*"FastAPI (>= 0.116) represents routers registered via `include_router`
with an internal `_IncludedRouter` object..."*), and requires
`starlette>=1.0.0,<2.0.0` — compatible with fastapi's own preferred
`1.6.0`, no downgrade forced. Repinned `pyproject.toml` to `8.1.0`.
Not a re-decision of Open Question 1 (the library choice itself is
unchanged) — a version correction found during Plan-time verification,
disclosed rather than silently swapped in.

### Deviation 2 — test-hygiene bug, found and fixed before finalizing

`test_metrics_returns_all_four_required_metric_families` originally
created a complaint via `POST` and never deleted it — every other test in
both `test_routes_complaints.py` and `test_routes_metrics.py` cleans up in
a `finally`; this one didn't. Confirmed the leak directly (`SELECT count(*)
FROM complaints` went from 36 seed rows to 37 after one run) and fixed it
to match house style before this commit.

### Verification — real output, pasted in full

**`ruff check .`** (local venv, after repinning to `8.1.0`):
```
All checks passed!
```

**`mypy app`**:
```
Success: no issues found in 31 source files
```

**Full suite, inside a container joined to `assign_1_internal` (same
established pattern as Phases 6-7 — `docker compose up -d postgres redis`,
`alembic upgrade head`, seed script, then `pytest` in a container on the
network, not on the host, since `compose.yaml` publishes no DB/cache
ports):**
```
======================= 155 passed, 2 warnings in 1.46s ========================
```
(153 from Phase 7 + 2 new: both `test_routes_metrics.py` cases.)

**Standalone new-test run** (`pytest tests/test_routes_metrics.py -v`):
```
tests/test_routes_metrics.py::TestMetricsEndpoint::test_metrics_returns_all_four_required_metric_families PASSED [ 50%]
tests/test_routes_metrics.py::TestMetricsEndpoint::test_fallback_counter_increments_on_provider_that_always_raises PASSED [100%]
======================== 2 passed, 2 warnings in 0.63s =========================
```

**Fallback-counter delta, real values** (ad-hoc script against the real app,
not summarized):
```
before: 0.0
POST status: 201 triaged_by: rules:fallback used_fallback: True
after: 1.0
delta: 1.0
```

**Services-layer `used_fallback` assertions** (extended, not new, tests —
part of the 155-pass run above): `test_submit_complaint_with_simulated_provider_round_trips`
and `test_submit_complaint_with_rule_based_provider_round_trips` both assert
`created["used_fallback"] is False`; `test_provider_that_always_raises_falls_back_deterministically`
asserts `is True`. All three pass (see full-suite output above).

**Manual verification against the built image** (`civicpulse-backend:dev`,
via `docker compose up -d --build backend`, hit from a container joined to
`assign_1_internal` since `backend` publishes no host port — real
`GET /metrics` output, truncated to the relevant families; full output
included every Python/process default metric too):
```
# HELP triage_latency_seconds Time spent in the triage provider call, in seconds.
# TYPE triage_latency_seconds histogram
triage_latency_seconds_bucket{le="0.005"} 1.0
...
triage_latency_seconds_count 1.0
triage_latency_seconds_sum 0.0

# HELP triage_fallback_total Count of complaints triaged via the rules-based fallback.
# TYPE triage_fallback_total counter
triage_fallback_total 0.0

# HELP http_requests_total Total number of requests by method, status and handler.
# TYPE http_requests_total counter
http_requests_total{handler="/health",method="GET",status="2xx"} 2.0
http_requests_total{handler="/api/complaints",method="POST",status="2xx"} 1.0

# HELP http_request_duration_seconds Latency with only few buckets by handler. Made to be only used if aggregation by handler is important.
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{handler="/api/complaints",le="0.1",method="POST"} 1.0
...
http_request_duration_seconds_sum{handler="/api/complaints",method="POST"} 0.06866313307546079
```
All four CONTRACTS.md §2.2 metrics present and real: request count
(`http_requests_total`), request latency histogram
(`http_request_duration_seconds`), triage latency (`triage_latency_seconds`),
fallback counter (`triage_fallback_total`).

**Cleanup confirmed:** every row created during verification (route-level
tests, the ad-hoc fallback script, the manual `docker compose` POST) was
deleted afterward; `SELECT count(*) FROM complaints` back to exactly 36
(the seed count) before tearing down. Ephemeral test-runner container and
the `docker compose` stack both removed (`docker rm -f`,
`docker compose down`); named volumes (`pgdata`, `redisdata`) left intact.

### Three-failure-mode audit

- **Silent decisions:** none beyond what OQ1/OQ2/the docstring rider
  already settled — the `prometheus-fastapi-instrumentator` version bump
  (7.1.0 → 8.1.0) is disclosed above as a correction, not left implicit;
  the dropped `routes/metrics.py` file was already disclosed in the
  Plan-commit round, not re-litigated here.
- **Unverified claims:** none — every Verification-required item above is
  real, pasted command/script output, not a summary or an assertion of
  success without evidence.
- **Undisclosed scope creep:** none. Touched exactly the Plan's five files
  plus the two test files the Plan already named as implementation-time
  choices. `RUBRIC-CHECKLIST.md`'s bonus line and `OPEN-DECISIONS.md` were
  updated as explicitly instructed this round, not as unrequested extras.
