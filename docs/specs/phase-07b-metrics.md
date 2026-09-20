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
- `GET /metrics` route (`backend/app/routes/metrics.py`), returning
  Prometheus text format with the correct `Content-Type`, registered in
  `main.py` alongside the existing routers.
- Generic instrumentation covering every request automatically:
  - **request count** — CONTRACTS.md §2.2: "request count"
  - **request latency histogram** — CONTRACTS.md §2.2: "request latency histogram"

  This is cross-cutting and applies to all routes without per-route code —
  ASGI middleware, registered in `main.py`. Exact library/shape deferred to
  Open Question 1, not decided here.
- Triage-specific instrumentation, recorded from inside or immediately beside
  `submit_complaint()` in `backend/app/services/complaints.py` (the only
  place both the triage result and its timing exist — `time.monotonic()`
  timing at line 53/66, fallback branch at lines 54-65):
  - **triage latency** — CONTRACTS.md §2.2: "triage latency" (the existing
    `triage_latency_ms` computation already measures this; the delta is
    recording it into a Prometheus histogram, not computing it fresh)
  - **fallback counter** — CONTRACTS.md §2.2: "fallback counter", incremented
    exactly when the existing `except Exception` branch runs (the same
    branch that already does `logger.warning("triage_provider_raised_falling_back", ...)`)

  Exactly these four metrics — no fifth metric invented, none of the four dropped.
- Wiring in `backend/app/main.py`: middleware registration (first
  `app.add_middleware` call in the app) and the new router include, following
  the existing flat-list house style already used for `health_router`,
  `complaints_router`, `meta_router`, `stats_router`.

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
1. **Library choice.** No metrics library is pinned in `backend/pyproject.toml`
   today. Recommendation: add `prometheus-fastapi-instrumentator` as the one
   new dependency. It wraps `prometheus_client` (which it pulls in
   transitively, so no second new dependency is needed) and gives request
   count + request latency histogram in ~3 lines
   (`Instrumentator().instrument(app).expose(app)`), satisfying the generic
   half of the Deliverables with the least code. The triage-specific pair
   (latency histogram, fallback counter) has no off-the-shelf coverage from
   either library — those are hand-declared `prometheus_client.Histogram`/
   `Counter` objects, using the dependency instrumentator already brought in.
   Needs approval before it's added to `pyproject.toml`.
2. **Where the triage-specific hook lives.** Proposed: directly inside
   `submit_complaint()` in `services/complaints.py`, next to the existing
   `time.monotonic()` timing and the `except Exception` fallback branch —
   the same function already does an infrastructure aside for logging
   (`logger.warning(...)`, line 57) from inside business-logic code, so
   recording a metric here is the same category of side effect with the
   same justification, not a new violation of the four-layer rule. Flagging
   explicitly for sign-off rather than treating it as self-evidently fine,
   since it's still `services/` importing something metrics-shaped.
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
(empty — pending human review of the above)

## Verification required
(to be filled in once Plan is approved; must include, at minimum, a real
behavioral test: POST /api/complaints with
`app.dependency_overrides[get_triage_provider] = lambda: SimulatedTriage(always_raise=True)`
— the same mechanism as Phase 7's mandatory Determinism test — followed by
GET /metrics, asserting the fallback counter's value actually incremented
in the returned Prometheus text, not merely that the endpoint returns
Prometheus-shaped text.)

## Ambiguity handling
If anything here conflicts with CONTRACTS.md or is underspecified, stop and
ask — do not silently resolve.

## As-Built
(empty)
