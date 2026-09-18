# Implementation plan — remaining phases

The map, not the itinerary: each phase still gets its own written spec, approved before code, per the workflow contract in `CLAUDE.md`. This document exists to fix the *order* and *why that order* up front, so later phase specs don't relitigate sequencing. Rubric categories are `docs/RUBRIC-CHECKLIST.md`'s A–J; a phase can (and mostly does) earn marks in more than one.

Ordered by dependency, not by rubric letter — B (Frontend) and H (Kubernetes) both land late because both need a stable thing to point at first.

## Phase 3 — Data layer

**Depends on:** nothing new (Phase 2's Alembic scaffold, zero migrations).
**Unlocks:** everywhere else — no other phase can persist anything without this.
**Rubric:** D (12) directly; unblocks C, E, F, J.

- One Alembic migration for the full schema (`docs/architecture/SCHEMA.md` / `docs/CONTRACTS.md`) — no DDL in app startup, per `CLAUDE.md`.
- Idempotent seed script: ≥30 realistic complaints, Urdu-influenced English (per the assignment's own flavor requirement), safe to re-run without duplicating rows.
- **Done looks like:** `alembic upgrade head` on a fresh DB succeeds; seed script run twice leaves the same row count; a manual `psql` query against the seeded table matches the schema doc.

## Phase 4 — Repository layer

**Depends on:** Phase 3 (schema must exist to query against).
**Unlocks:** services (Phase 6) — they call repositories, not SQL.
**Rubric:** D, unblocks C.

- Complaint CRUD, filtering, pagination.
- Stats aggregation queries (counts by category/priority/status — whatever `/api/stats` needs per `docs/CONTRACTS.md`).
- No business rules here — just persistence, per the four-layer rule.
- **Done looks like:** a `pytest` suite against a real (test) Postgres exercises every repository method directly, no HTTP layer involved.

## Phase 5 — Triage providers (deterministic first, LLM second)

**Depends on:** nothing from Phases 3–4 — this is the most self-contained slice (`docs/PARALLEL-WORK-PLAN.md` already says so), gated only by the `TriageProvider` Protocol (ADR 0001).
**Unlocks:** service-layer triage orchestration (Phase 6) and CI determinism (Phase 11 needs `SimulatedTriage` to exist first).
**Rubric:** F (25 — the single largest category); unblocks C, I.

Split into two sub-phases because they have genuinely different risk profiles:

- **5a — `RuleBasedTriage` + `SimulatedTriage`:** deterministic, no network calls, no API key needed. Doing these first means CI can be wired up and made green immediately, rather than waiting on a working Gemini integration.
- **5b — `LLMTriage`:** Gemini client, hybrid PII redaction (ADR 0004) applied before any text leaves the process, timeout/retry/fallback-to-`RuleBasedTriage` wrapper (per `docs/CONTRACTS.md`), `triaged_by = "llm:gemini"` (`DEVIATIONS.md`).
- `OllamaTriage` fits in 5b's slot too (same "external, needs a wrapper" shape) but is lower priority than getting `LLMTriage` correct — sequence within 5b when we get there.
- **Done looks like:** unit tests instantiate each provider directly (no HTTP, no DB) and assert on `TriageResult` shape; a manual run against a live Gemini key produces a sane result; killing network access to the LLM provably falls back to `RuleBasedTriage` rather than 500ing.

## Phase 6 — Service layer

**Depends on:** Phase 4 (repositories) and Phase 5a at minimum (needs at least one working provider to orchestrate against; doesn't need 5b yet).
**Unlocks:** routes (Phase 7).
**Rubric:** C (25); unblocks E, F (orchestration half).

- Status state machine (valid transitions, 409 on invalid ones per `docs/CONTRACTS.md`).
- Triage orchestration: calls the provider via the factory (ADR 0001), never a concrete class.
- Statistics logic (whatever shaping happens above the raw repository aggregation query).
- **Done looks like:** service-level tests use `SimulatedTriage` and a real test DB (or a fake repository), assert the state machine rejects invalid transitions, no FastAPI involved yet.

## Phase 7 — Routes

**Depends on:** Phase 6 (services must exist to wire routes to).
**Unlocks:** frontend (Phase 9) and cache layer wiring (Phase 8, since rate-limiting sits in front of a real route).
**Rubric:** C (25, completes it); unblocks B, E.

- All remaining endpoints from `docs/CONTRACTS.md` wired to services.
- Request validation (Pydantic models), error response shapes exactly as contracted (including the 409 transition-error body).
- **Done looks like:** `httpx`/`TestClient` integration tests hit every route end-to-end against a test DB with `SimulatedTriage`; OpenAPI schema (`/docs`, `/openapi.json`) reflects the real contract, ready for the frontend to codegen or hand-type a client against.

## Phase 8 — Cache layer

**Depends on:** Phase 7 (rate limiter wraps a real `POST /api/complaints`; stats caching wraps a real `/api/stats`).
**Unlocks:** nothing downstream is blocked by this — it's an enhancement to existing routes, which is why it comes after routes exist rather than before.
**Rubric:** E (10).

- `/api/stats` read-through caching + invalidation on writes that change the aggregate.
- Redis-backed fixed-window rate limiter (`docs/OPEN-DECISIONS.md` #7) on `POST /api/complaints`.
- **Done looks like:** a test hammers the rate-limited endpoint past its quota and gets 429; a stats-cache test writes a complaint, confirms the cached value is invalidated (not stale) on the next read; `X-Cache` header present per contract.

## Phase 9 — Frontend real views

**Depends on:** Phase 7 (needs a stable, real API contract to build against — not a moving target). Can start against the OpenAPI schema slightly earlier if it's frozen, but building against Phase 2's placeholder would mean rework.
**Unlocks:** nothing else — leaf consumer, per `PARALLEL-WORK-PLAN.md`.
**Rubric:** B (18).

- Submit, Dashboard, Stats views; typed API client generated from or hand-typed against the OpenAPI schema.
- No duplicated business rules (status transition table, category/priority lists) — render what the backend returns, per `PARALLEL-WORK-PLAN.md`'s constraint on this slice.
- **Done looks like:** manual browser walkthrough — submit a complaint, see it appear on the dashboard, see stats update; `npm run build`/`typecheck`/`lint` all green (already true for the skeleton, must stay true).

## Phase 10 — Docker/Compose hardening

**Depends on:** Phases 3–9 producing the real images this hardens (resource limits, network segmentation, and healthchecks are already done in Phase 2 — this phase re-verifies them against the now-real app, not the walking skeleton, and closes anything deferred).
**Unlocks:** Kubernetes manifests (Phase 11) — they reuse these same images.
**Rubric:** G (15, tops up what Phase 2 already earned); touches §5.3 deductions.

- Re-check `.dockerignore` effectiveness now that real source trees exist (not just the skeleton's few files).
- Digest pinning, if pursued — currently bonus scope (`docs/OPEN-DECISIONS.md` #10), decide when we revisit bonus before Phase 12.
- Re-run the network-segmentation proof (`frontend` → `postgres` ping) against the full app, not just the skeleton, since this is a graded proof point every time the compose files change materially.
- **Done looks like:** same live verification loop as Phase 2's Part D, rerun against the real app.

## Phase 11 — Kubernetes manifests

**Depends on:** Phase 10's images (k8s deploys images, not source).
**Unlocks:** CI/CD's `cd.yml` (Phase 12 needs manifests to deploy).
**Rubric:** H (20).

- Namespace, ConfigMap/Secret, Deployments (backend, frontend), StatefulSet (postgres, per `PARALLEL-WORK-PLAN.md`'s own naming), Services, HPA/VPA/PDB, Kustomize base + overlays/dev + overlays/prod (`CLAUDE.md` tech stack).
- PostgreSQL gets a PVC (§5.3 deduction if it doesn't).
- No LLM key in any committed manifest, even base64 (§5.3 deduction) — Secret is templated/injected, never committed with a real value.
- **Done looks like:** `k3d` local cluster, `kubectl apply -k overlays/dev` brings the whole stack up healthy; HPA visibly scales replicas under the k6 load test (needed for the replicas-vs-load chart, `docs/OPEN-DECISIONS.md` #8).

## Phase 12 — CI/CD

**Depends on:** Phase 11 (cd.yml deploys manifests that must already exist) and Phase 5a at minimum (ci.yml needs `SimulatedTriage` for deterministic test runs).
**Unlocks:** nothing further builds on this, but it's the last thing standing between "works on my machine" and "works from a clean clone/actions run."
**Rubric:** I (20); closes out §5.3 deductions (publish/deploy jobs gated by `needs:`, no `:latest` deployed).

- `ci.yml`: lint, typecheck, test (backend + frontend), build images.
- `cd.yml`: gated by `needs:` on `ci.yml` passing; deploy-by-SHA (ADR 0003) — never `:latest`.
- `release.yml`: publish to GHCR with an SBOM via Syft.
- **Revisit bonus scope here** (`docs/OPEN-DECISIONS.md` #10, `CLAUDE.md` "still open") — this is the phase it was deferred to.
- **Done looks like:** a PR triggers `ci.yml` and it goes green; a merge to `dev`/`main` (per whatever branch policy exists by then) triggers `cd.yml`, which only runs if `ci.yml` passed, and deploys an image tagged with the real commit SHA.

## Phase 13 — Documentation close-out

**Depends on:** everything above existing in at least draft form — `PARALLEL-WORK-PLAN.md` already notes this slice "naturally trails the others."
**Unlocks:** nothing — this is the last phase.
**Rubric:** J (15); also the thing that makes every other category's evidence checkable (`docs/RUBRIC-CHECKLIST.md` evidence column needs real file-and-line citations per §5.2).

- README quickstart that actually works from a clean clone (§5.3 deduction if it doesn't — test this literally, in a fresh clone, not from the dev tree).
- RUNBOOK, ENGINEERING-NOTES, AI-USAGE.
- Any remaining ADRs (decisions made along the way that weren't pre-registered as ADRs 0001–0005).
- Evidence screenshots for `docs/evidence/`.
- Final pass over `docs/RUBRIC-CHECKLIST.md` — fill in only what's genuinely true, same discipline as every phase so far.
- **Done looks like:** a literal fresh `git clone` + README steps, on a machine with nothing pre-configured, produces a working local stack.

## Sequencing notes

- **5a before 6, not 5 (whole) before 6:** service-layer + route-layer work and CI can both start against `SimulatedTriage`/`RuleBasedTriage` well before Gemini integration (5b) is done — no reason to block the bulk of the backend on an external API key/network dependency.
- **9 (Frontend) deliberately late:** building it against Phase 2's placeholder API would mean redoing it once the real contract firms up in Phase 7. `PARALLEL-WORK-PLAN.md` notes the frontend *can* start once the OpenAPI schema is stable — if it stabilizes early during Phase 7, Phase 9 can overlap with Phase 8, not strictly wait for it.
- **10 before 11, not skipped:** Kubernetes deploys the images Docker builds — hardening the images before writing manifests around them avoids re-editing manifests when an image-layer issue surfaces later.
- **12 last among build phases:** CI/CD automates everything before it; automating an unstable pipeline just means the failures show up in Actions logs instead of a terminal.
