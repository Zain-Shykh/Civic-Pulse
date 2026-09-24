# Phase 10: Docker/Compose hardening
Status: in progress
Depends on: Phases 3-9 (and 9c) — this phase hardens the images/compose shape those phases produced, against the real app, not the Phase 2 walking skeleton.
Reads first: `docs/IMPLEMENTATION-PLAN.md`'s Phase 10 entry, `docs/OPEN-DECISIONS.md` #11, `docs/adr/0001-triage-provider-interface.md`, `docs/adr/0003-deploy-by-sha.md`, `compose.prod.yaml`, `compose.yaml`, `backend/.dockerignore`, `frontend/.dockerignore`

## Goal
Close the two things `docs/IMPLEMENTATION-PLAN.md`'s Phase 10 entry names as still open — `compose.prod.yaml`'s backend has no `TRIAGE_PROVIDER`/`GEMINI_API_KEY` at all, and `.dockerignore` effectiveness hasn't been re-checked since Phase 2's skeleton — and re-verify, against the real (not skeleton) app, the network-segmentation proof this project treats as a graded proof point every time compose changes materially.

## Deliverables

**a. `compose.prod.yaml` — fail-fast on missing `TRIAGE_PROVIDER`/`GEMINI_API_KEY`**

Confirmed directly (grep of the file): the backend service's `environment:` block has neither name today. Confirmed directly in code: `get_triage_provider()` (`backend/app/providers/triage/factory.py:44`) reads `os.environ["TRIAGE_PROVIDER"]` with no `.get()`/default — so if the var is entirely absent from the container's environment, the app already crashes at startup with `KeyError` (ADR 0001's "an unrecognized value should fail fast at startup" already covers *absent/bad* `TRIAGE_PROVIDER`, just not cleanly — a raw traceback, not an actionable message). But `GEMINI_API_KEY` has no equivalent protection at all: `Settings.gemini_api_key` (`backend/app/config.py:15`) defaults to `""`, and `LLMTriage.__init__` (`backend/app/providers/triage/llm.py:74`) never validates the key it's given — `genai.Client(api_key="")` constructs without error. If `TRIAGE_PROVIDER=llm` but `GEMINI_API_KEY` is unset in prod, the app starts up reporting healthy, and every real triage call fails auth silently, falling back to `rules:fallback` (`llm.py`'s own `except (httpx.TimeoutException, errors.APIError)` branch, which doesn't distinguish "bad key" from "Gemini is down") forever — a citizen-facing behavior change with no operator-visible signal that the intended `LLMTriage` never actually ran once.

Mechanism: add both as Compose's own *required-variable* interpolation, `${VAR:?message}`, in `compose.prod.yaml`'s backend `environment:` block:

```yaml
environment:
  DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
  REDIS_URL: redis://redis:6379/0
  TRIAGE_PROVIDER: ${TRIAGE_PROVIDER:?TRIAGE_PROVIDER must be set for a production deploy — see docs/adr/0001-triage-provider-interface.md}
  GEMINI_API_KEY: ${GEMINI_API_KEY:?GEMINI_API_KEY must be set for a production deploy}
```

This is a stronger fail-fast than the app-level `KeyError`: Compose itself refuses to resolve the compose file (errors on `docker compose up`/`config`/`build` before any container is created), with a message naming the actual missing variable — not a container that gets created, starts, crash-loops, and needs a `docker logs` round-trip to diagnose. No app code changes needed; `compose.yaml` (dev) is untouched, since dev's own `TRIAGE_PROVIDER=rules` default (`dd8ecd9`) is a deliberate, already-approved, separate decision for local iteration.

Also confirmed directly: `.env.example` documents `TRIAGE_PROVIDER` only under its "compose.yaml (dev) only" section, and never mentions `GEMINI_API_KEY` at all — so nothing today tells whoever copies `.env.example` → `.env` for a prod-shaped run that both are now mandatory. Add a section:

```
# --- compose.prod.yaml only: triage provider (required, no default — Compose itself errors if unset) ---
TRIAGE_PROVIDER=llm
GEMINI_API_KEY=your-gemini-api-key-here
```

placed next to the existing "compose.prod.yaml only: image source" block, not the dev one — dev keeps its own separate `TRIAGE_PROVIDER=rules` line unchanged.

**b. `.dockerignore` corrections**

Confirmed directly (`find`/`du` against the real source trees, post Phase 8/9/9c): `frontend/.dockerignore` needs no changes — `node_modules`, `dist`, `tests`, `.env*` are all still the complete real list of what shouldn't reach the build context; nothing Tailwind/shadcn added (`components.json`, the extra `tsconfig.*.json` files, `src/lib`, `src/components/ui`) is excludable, all of it is needed by the frontend Dockerfile's build stage.

`backend/.dockerignore` has a real, if minor, gap: two untracked directories now exist in the real backend tree that the current list doesn't cover — `build/` (152K) and `civicpulse_backend.egg-info/` (24K), both local packaging artifacts from `pip install -e .`/editable installs, neither referenced by `backend/Dockerfile` (which `COPY`s only `pyproject.toml`, `app`, `alembic`, `alembic.ini` — confirmed by reading the Dockerfile directly). They never reach the built image regardless, but `.dockerignore`'s job is trimming the build context sent to the daemon, not just what an explicit `COPY` picks up — add both:

```
build
*.egg-info
```

**c. Network-segmentation proof, re-verified against the real app**

Ran for real, not re-read from a prior phase's report (`docker compose up -d --build` against the current `compose.yaml`, i.e. the real backend/frontend images with Phase 3-9c's actual code, not the Phase 2 skeleton):

```
$ docker compose up -d --build
 Image civicpulse-backend:dev   Built
 Image civicpulse-frontend:dev  Built
 Container assign_1-postgres-1  Healthy
 Container assign_1-redis-1     Healthy
 Container assign_1-backend-1   Healthy
 Container assign_1-frontend-1  Healthy

$ docker compose ps
NAME                  IMAGE                     SERVICE    STATUS
assign_1-backend-1    civicpulse-backend:dev    backend    Up (healthy)
assign_1-frontend-1   civicpulse-frontend:dev   frontend   Up (healthy)
assign_1-postgres-1   postgres:16-alpine        postgres   Up (healthy)
assign_1-redis-1      redis:7-alpine            redis      Up (healthy)

$ docker compose exec backend python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health'); print(r.status, r.read().decode())"
200 {"status":"ok"}

$ docker compose exec backend python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/ready'); print(r.status, r.read().decode())"
200 {"status":"ready"}

$ docker compose exec frontend ping -c 2 postgres
ping: bad address 'postgres'
$ echo $?
1

$ docker compose exec frontend ping -c 2 redis
ping: bad address 'redis'
$ echo $?
1
```

`ping` fails at DNS resolution ("bad address"), not merely "no route" — confirming `frontend` isn't on the `internal` network at all (can't even resolve the service name), the strongest form of the segmentation proof. (No `curl` binary exists in the `python:3.12-slim`-based runtime image — used Python's own `urllib` for the in-container health checks instead, matching the exact call the Dockerfile's own `HEALTHCHECK` line already makes.) One correction versus Phase 2's original spec text: that spec said `ping database` — the actual Compose service name has always been `postgres` (confirmed directly in `compose.yaml`), not `database`; used the real name here.

Stack torn down after verification (`docker compose down`) — no lingering containers, no test data was written (this was a pure connectivity/health check, no `/api/complaints` calls), so no DB cleanup is needed this time.

## Non-goals
- Digest pinning — explicitly deferred (`docs/IMPLEMENTATION-PLAN.md`'s own Phase 10 text: "currently bonus scope, decide when we revisit bonus before Phase 12"). Not decided here, either way.
- No changes to `compose.yaml` (dev) — its `TRIAGE_PROVIDER=rules` default and lack of a `GEMINI_API_KEY` requirement are unchanged; dev is deliberately more forgiving than prod.
- Actually standing up Prometheus/Grafana, or adding a Prometheus service to any compose file — see Open Question 1. This phase decides the *shape* the compose files would need if that bonus is pursued, not whether to pursue it (that's `docs/OPEN-DECISIONS.md` #10, still open, deferred to before Phase 12).
- No Kubernetes manifest work (Phase 11's scope).
- No change to `.env` itself (gitignored, machine-local) beyond what `.env.example` documents as a placeholder.

## Open Questions

**1. Does this phase resolve `docs/OPEN-DECISIONS.md` #11 (Prometheus can't reach `/metrics`)?**

Recommendation: resolve the *architectural* question now, defer the *execution*. The two candidates named in #11 are (a) publish a backend host port in `compose.yaml`, or (b) run Prometheus itself as a compose service on the `edge` network, reaching `backend` by service name.

(b) is the better answer, for the same reason `frontend` already reaches `backend` by service name instead of a published port: it needs zero new host-port surface, stays consistent with the segmentation model this phase just re-verified, and sidesteps relitigating whether a published backend port would ever brush up against §5.3's port-publishing deduction (that deduction is explicitly about a *database or cache* port in `compose.prod.yaml`, so a backend API port likely isn't covered at all — but "likely not covered" is a weaker position than "never came up because no port was published").

Not executed in this phase's Deliverables: actually adding a `prometheus` service (plus its scrape config, plus Grafana, plus a dashboard/screenshot) is bonus-item work gated behind `docs/OPEN-DECISIONS.md` #10 ("which bonus items to pursue," still open, explicitly deferred to "revisit before the CI/CD phase" by `CLAUDE.md` itself). Building it now would be undisclosed scope creep into a decision this project has already agreed not to make yet. So: #11 is resolved as "if pursued, run Prometheus as an `edge`-network compose service, no new published port" — carried forward only as *execution*, not left ambiguous as *design*.

**2. Should `GEMINI_API_KEY` be unconditionally required in `compose.prod.yaml`, even if someone sets `TRIAGE_PROVIDER` to `rules`/`simulated` for a prod-shaped test run?**

Recommendation: yes, require both unconditionally. `compose.prod.yaml` exists to model exactly one real deployment shape — the one that actually runs `LLMTriage` — not a general-purpose "prod or prod-like" toggle. Making `GEMINI_API_KEY` conditionally required (only if `TRIAGE_PROVIDER=llm`) needs either a shell wrapper script or Compose profiles to express, which is more moving parts than this problem is worth; the plain `${VAR:?msg}` form deliberately trades a small amount of flexibility (can't spin up prod-shaped compose with `rules` and no key) for a one-line, un-bypassable check. If a genuine need for a keyless prod-shaped smoke test shows up later, that's a real decision to flag then, not a hypothetical to build against now.

## Verification required

Exact commands (matching Phase 2's own Part D loop, against the real app, plus the two new checks this phase adds):

1. `docker compose config` against `compose.prod.yaml` with `GEMINI_API_KEY`/`TRIAGE_PROVIDER` unset in the environment — must error, quoting the message from Deliverable (a), before anything is built or started.
2. `docker compose config` against `compose.prod.yaml` with both set — must succeed (no error), confirming the required-var syntax doesn't break the happy path.
3. `docker compose up -d --build` against `compose.yaml` (real app) — all four containers reach `healthy`.
4. `docker compose exec backend python -c "...urlopen('http://127.0.0.1:8000/health')..."` — `200 {"status":"ok"}`.
5. `docker compose exec backend python -c "...urlopen('http://127.0.0.1:8000/ready')..."` — `200 {"status":"ready"}`.
6. `docker compose exec frontend ping -c 2 postgres` — fails (DNS resolution failure).
7. `docker compose exec frontend ping -c 2 redis` — fails (DNS resolution failure).
8. `docker compose down` — clean teardown, no orphaned containers/volumes beyond the named ones already tracked.

## Ambiguity handling
If anything here conflicts with `CONTRACTS.md`, any ADR, or is underspecified, stop and ask — do not silently resolve.

## Plan

## As-Built
