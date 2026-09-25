# Phase 10: Docker/Compose hardening
Status: done
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

**Decided:** (b), exactly as recommended above. If the Prometheus/Grafana bonus item is ever pursued, Prometheus runs as its own compose service on the `edge` network, scraping `backend:8000/metrics` by Docker service name — the same mechanism `frontend` already uses to reach `backend`. No published host port on `backend`, ever, for this purpose. This is an architecture decision only: no `prometheus` service, scrape config, Grafana, or related compose/dependency change lands in this phase — execution stays gated behind `docs/OPEN-DECISIONS.md` #10. `docs/OPEN-DECISIONS.md` #11 itself has been updated to record this resolution (see that file).

**2. Should `GEMINI_API_KEY` be unconditionally required in `compose.prod.yaml`, even if someone sets `TRIAGE_PROVIDER` to `rules`/`simulated` for a prod-shaped test run?**

Recommendation: yes, require both unconditionally. `compose.prod.yaml` exists to model exactly one real deployment shape — the one that actually runs `LLMTriage` — not a general-purpose "prod or prod-like" toggle. Making `GEMINI_API_KEY` conditionally required (only if `TRIAGE_PROVIDER=llm`) needs either a shell wrapper script or Compose profiles to express, which is more moving parts than this problem is worth; the plain `${VAR:?msg}` form deliberately trades a small amount of flexibility (can't spin up prod-shaped compose with `rules` and no key) for a one-line, un-bypassable check. If a genuine need for a keyless prod-shaped smoke test shows up later, that's a real decision to flag then, not a hypothetical to build against now.

**Decided:** Option A, exactly as recommended and exactly as already drafted in Deliverable (a) — `${TRIAGE_PROVIDER:?...}` and `${GEMINI_API_KEY:?...}`, both unconditional, no conditional logic, no Compose profiles, no wrapper script. `compose.prod.yaml` must refuse to start with either variable missing, regardless of which triage provider is selected. No change to Deliverable (a)'s already-drafted mechanism.

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

Three files touched, in this order — each is independent of the others, ordered by dependency between the fail-fast fix and its own documentation, then the unrelated `.dockerignore` cleanup last:

**1. `compose.prod.yaml`** — edit only the `backend` service's existing `environment:` block (lines confirmed current, re-checked against the real file this session, not assumed from the earlier spec draft). Add two keys after the existing `DATABASE_URL`/`REDIS_URL` lines:

```yaml
      TRIAGE_PROVIDER: ${TRIAGE_PROVIDER:?TRIAGE_PROVIDER must be set for a production deploy — see docs/adr/0001-triage-provider-interface.md}
      GEMINI_API_KEY: ${GEMINI_API_KEY:?GEMINI_API_KEY must be set for a production deploy}
```

No other line in the file changes — `frontend`/`postgres`/`redis` services, networks, volumes, resource limits all stay exactly as they are today.

**2. `.env.example`** — add one new section, placed immediately after the existing "compose.prod.yaml only: image source" block (re-checked current content this session — it still has no `GEMINI_API_KEY` line anywhere, confirming the spec's earlier finding wasn't stale):

```
# --- compose.prod.yaml only: triage provider (required, no default — Compose itself errors if unset) ---
TRIAGE_PROVIDER=llm
GEMINI_API_KEY=your-gemini-api-key-here
```

The existing dev section's `TRIAGE_PROVIDER=rules` line is untouched — two different variables sharing a name across two sections is already how `POSTGRES_*` works in this same file (shared section) and how `IMAGE_TAG` is prod-only today, so this isn't a new pattern.

**3. `backend/.dockerignore`** — append two lines (re-checked current content this session — still the same 16 lines as the spec draft found, no drift):

```
build
*.egg-info
```

No changes to `frontend/.dockerignore` (confirmed, again, still correct as-is).

**Verification, run after all three edits land:**

The 8 commands already listed under "Verification required" above, run for real and pasted into As-Built — not reused from the spec-drafting session's output, since the `.dockerignore` edit means a fresh `--build` produces a genuinely new image, and the `compose.prod.yaml`/`.env.example` edits are entirely new behavior that's never been exercised.

For commands 1–2 (`docker compose config` against `compose.prod.yaml`, once failing, once succeeding), the repo's real `.env` already exists and may already define `GEMINI_API_KEY`/`TRIAGE_PROVIDER` for dev use — using it unmodified would contaminate the "missing variable" test. Isolate with two throwaway env files instead of touching the real `.env`:
- a "missing" scratch file defining only `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`/`GHCR_NAMESPACE`/`IMAGE_TAG`, deliberately omitting `TRIAGE_PROVIDER`/`GEMINI_API_KEY`
- a "complete" scratch file with the same plus `TRIAGE_PROVIDER=llm` and a dummy `GEMINI_API_KEY` value (never a real key — this only exercises Compose's variable substitution, no container starts, no Gemini call happens)

both passed via `docker compose --env-file <scratch>.env -f compose.prod.yaml config`, both scratch files written under the job's tmp directory, neither committed.

For commands 3–8 (the real `docker compose up -d --build` loop against dev `compose.yaml`), no scratch file trick is needed — this is the same real app, same real `.env`, same procedure already run once for the spec draft; rerunning it just confirms the `.dockerignore` change didn't break anything. As before: no `/api/complaints` calls happen during this pass, so no DB cleanup is needed afterward; `docker compose down` after, same as last time.

Nothing here is uncertain — all three edits are single, small, mechanical changes to files already fully read this session; the only judgment calls (the `${VAR:?msg}` mechanism, unconditional requirement, Prometheus architecture) were already made and recorded above as the two Open Questions' decisions.

## As-Built

Implemented exactly the three files the Plan named. Commit `815be7e` (`fix:` — chosen over `feat:` because this hardens existing, already-shipped prod-compose behavior rather than adding new functionality).

**`git diff --stat` for the implementation commit** (confirms no scope beyond the Plan):
```
.env.example          | 4 ++++
backend/.dockerignore | 2 ++
compose.prod.yaml     | 2 ++
3 files changed, 8 insertions(+)
```

**Verification — all 8 commands, real output:**

1. `docker compose --env-file <scratch-missing>.env -f compose.prod.yaml config` (isolated scratch file defining only `POSTGRES_*`/`GHCR_NAMESPACE`/`IMAGE_TAG`, deliberately omitting `TRIAGE_PROVIDER`/`GEMINI_API_KEY`) — failed as required, exit 1:
   ```
   error while interpolating services.backend.environment.GEMINI_API_KEY: required variable GEMINI_API_KEY is missing a value: GEMINI_API_KEY must be set for a production deploy
   error while interpolating services.backend.environment.TRIAGE_PROVIDER: required variable TRIAGE_PROVIDER is missing a value: TRIAGE_PROVIDER must be set for a production deploy — see docs/adr/0001-triage-provider-interface.md
   ```
   Note: Compose wraps the custom `:?` message in its own `error while interpolating services.backend.environment.<VAR>: required variable <VAR> is missing a value:` prefix. The spec's Deliverable (a) only ever specified the custom message text itself (the part after that prefix), which matches verbatim; the wrapper phrasing is Compose's own format, not something this phase authored or predicted.

2. Same command against a "complete" scratch file (same base plus `TRIAGE_PROVIDER=llm`, `GEMINI_API_KEY=dummy-value-for-config-check-only`) — succeeded, exit 0, full config rendered correctly, e.g.:
   ```yaml
   environment:
     DATABASE_URL: postgresql+psycopg://civicpulse:change-me@postgres:5432/civicpulse
     GEMINI_API_KEY: dummy-value-for-config-check-only
     REDIS_URL: redis://redis:6379/0
     TRIAGE_PROVIDER: llm
   image: ghcr.io/OWNER/civicpulse-backend:latest
   ```
   Both scratch files lived under the job's tmp directory only, never committed, never touching the repo's real `.env`.

3. `docker compose up -d --build` against the real dev `compose.yaml` (fresh context — `backend/.dockerignore` changed) — all four containers reached `healthy`:
   ```
   assign_1-backend-1    civicpulse-backend:dev    Up (healthy)
   assign_1-frontend-1   civicpulse-frontend:dev   Up (healthy)
   assign_1-postgres-1   postgres:16-alpine        Up (healthy)
   assign_1-redis-1      redis:7-alpine            Up (healthy)
   ```

4. `docker compose exec backend python -c "...urlopen('http://127.0.0.1:8000/health')..."` → `200 {"status":"ok"}`

5. `docker compose exec backend python -c "...urlopen('http://127.0.0.1:8000/ready')..."` → `200 {"status":"ready"}`

6. `docker compose exec frontend ping -c 2 postgres` → `ping: bad address 'postgres'`, exit 1

7. `docker compose exec frontend ping -c 2 redis` → `ping: bad address 'redis'`, exit 1

8. `docker compose down` — clean teardown, all containers/networks removed, no orphans. No `/api/complaints` calls were made during this pass, so no seeded-DB row cleanup was needed (unlike prior phases' verification passes).

**Deviations from Plan or Spec:** none. All three edits match the Plan's exact diffs; the `docker compose config` wrapper-message wording (noted under command 1 above) is the only place real output differed at all from what the spec quoted, and it's Compose's own formatting around a message this phase did control and which matched exactly.

**Three-failure-mode audit:** no silent decisions (both Open Questions were resolved by the user before implementation, nothing re-decided here); no unverified claims (every result above is real, pasted command output, not a description); no undisclosed scope creep (`git diff --stat` above confirms exactly the three planned files, eight lines, nothing else).
