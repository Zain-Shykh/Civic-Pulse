# Parallel Work Plan (draft)

Living draft of natural task seams, sketched before any real phases exist. Refine this once actual phases are approved and underway — the point right now is just to confirm the module boundaries are clean enough that any slice below could be handed to a second person without them touching code outside it.

The seams follow the four backend layers (`CLAUDE.md`) plus the frontend/infra split already forced by the architecture (§2 of the assignment).

## Slice: Frontend (React + Vite + TS)

- **Owns:** `frontend/` — submit view, dashboard, stats view, typed API client, runtime config (`/config.js` or nginx proxy, per `docs/OPEN-DECISIONS.md`), component tests.
- **Depends on:** the backend's OpenAPI schema and the API contract in `docs/CONTRACTS.md` (routes, status codes, error shapes, the `X-Cache` header, the 409 transition-error body). Does not need a running backend to start — can build against a mocked/generated client from the OpenAPI schema once it's stable.
- **Must respect:** owns zero business rules — no duplicated status-transition table, no duplicated category/priority lists. Anything like that belongs in the backend and is only *rendered* here.
- **Interface it exposes to the rest of the system:** none — it's a leaf consumer.

## Slice: Backend API layer (routes + services)

- **Owns:** `backend/app/routes/`, `backend/app/services/` — request/response handling, the status state machine, statistics aggregation, orchestration of triage calls.
- **Depends on:** the `repositories/` interface (for persistence) and the `TriageProvider` interface (for triage) — not on their implementations.
- **Must respect:** the four-layer rule — no SQL in routes or services, no provider-specific logic (e.g. no Groq-specific code) outside `providers/`.
- **Interface it exposes:** the API contract in `docs/CONTRACTS.md` — this is what the frontend slice is built against.

## Slice: AI / triage providers

- **Owns:** `backend/app/providers/triage/` — `LLMTriage`, `OllamaTriage`, `RuleBasedTriage`, `SimulatedTriage`, the retry/timeout/fallback/cache wrapper, the prompt-injection guardrail.
- **Depends on:** nothing else in the codebase — only the `TriageProvider` Protocol and `TriageResult` schema (`docs/CONTRACTS.md`). This is the most self-contained slice in the project; it can be developed and unit-tested with zero knowledge of routes, the DB, or the frontend.
- **Must respect:** the `TriageProvider` interface signature exactly — `services/` calls providers only through that interface, never a concrete class.
- **Interface it exposes:** `TriageProvider.triage(text, location) -> TriageResult`, selected via `TRIAGE_PROVIDER` env var by a factory (`providers/triage/factory.py`).

## Slice: Data layer (migrations + repositories)

- **Owns:** `backend/alembic/`, `backend/app/repositories/` — schema, indexes, the seed command.
- **Depends on:** the schema table in `docs/CONTRACTS.md`. Independent of services/routes/providers.
- **Must respect:** every SQL statement lives here; repositories expose methods (e.g. `create_complaint`, `list_complaints(filters, page)`, `update_status`), never raw queries, to the services layer.
- **Interface it exposes:** the repository method signatures consumed by `services/`.

## Slice: Infra / DevOps (Docker, Compose, Kubernetes, CI/CD)

- **Owns:** both Dockerfiles, `compose.yaml` / `compose.prod.yaml`, `k8s/`, `.github/workflows/`, `load/k6-script.js`.
- **Depends on:** the application's *external* container contract only — not its internals: which port it listens on, `/health` and `/ready` semantics, required env vars / secrets (documented in `.env.example` and the ConfigMap/Secret), and the fact that graceful shutdown on SIGTERM is implemented.
- **Must respect:** never needs to read application code to do its job — if it does, the container contract is leaking.
- **Interface it exposes:** the running system itself (compose stack, k8s manifests) that every other slice is deployed into and tested against in CI.

## Slice: Docs / ADRs / evidence

- **Owns:** `docs/` — ADRs, `ENGINEERING-NOTES.md`, `RUNBOOK.md`, `AI-USAGE.md`, evidence screenshots.
- **Depends on:** decisions made by every other slice (can't document a decision that hasn't been made) — naturally trails the others, not a blocker for them.
- **Must respect:** nothing structurally, but content must cite real file-and-line references (per §5.2), so it needs the other slices to exist first, even in draft form.

## Suggested split if/when a partner joins

A specific person will probably join the project, but he has not started and there is no confirmed date — this plan has to work whether he joins in week 1, week 3, or never.

Two people, cutting along the seam with the least cross-talk: **frontend** as one person's track end-to-end (its only dependency is a stable contract, not stable code), and **backend + AI + data + infra** as the other's — or, if the second person is also backend-capable, split **AI/triage providers** (fully isolated) from **API layer + data layer + infra** as the second track. Avoid splitting along "backend vs infra" as the first cut — infra depends on backend's container contract being settled first, so it's a bad slice to hand off in parallel from day one.

**On timing:** the later he joins, the less runway there is to build the Category A collaboration evidence (§4-A) that needs sustained two-person history — merged PRs with his review, a commit-share floor, a real merge conflict. Handing him a slice from this plan the moment he's available is necessary but not sufficient; those rubric lines need contribution *over time*, not a single late burst of activity. See `docs/RUBRIC-CHECKLIST.md`.
