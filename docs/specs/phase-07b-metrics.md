# Phase 7b: Observability middleware
Status: not started
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
(empty)
