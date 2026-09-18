# CivicPulse — Project Constitution

Re-read this file at the start of every session, before doing anything else.

## Project summary

CivicPulse is a municipal complaint intake, triage and operations platform: a citizen submits a free-text complaint through a web frontend, a backend validates and triages it via a pluggable AI provider into a category, priority and one-line summary, persists it durably in PostgreSQL, and surfaces it on a live operations dashboard backed by Redis-cached aggregate stats — the whole system running as five cooperating containers locally via Docker Compose, and as a probed, autoscaling workload on Kubernetes in CI. This is CS4032 Assignment 1 ("Software Construction and Design"), 150 marks plus up to +15 bonus, full spec in `Software Construction and Design -  Assignment 1.md` at the repo root.

## The four-layer backend rule

Dependency arrows point one way only: `routes/` → `services/` → `repositories/` → `providers/`.

- `routes/` — HTTP only: parse, validate, serialise, status codes. No business rules.
- `services/` — business rules: triage orchestration, the status state machine, statistics.
- `repositories/` — persistence: all SQL lives here, and nowhere else.
- `providers/` — outbound integrations (LLM, cache), behind interfaces.

**A route that opens a database session is a design failure worth marks**, not a style nitpick. The moment a route touches the DB directly: the HTTP layer now knows about SQL, the business rules can no longer be tested without a live database, and the persistence strategy can't change without touching every route that used it. The four layers exist precisely so each one can be replaced or unit-tested in isolation — that's decomposition and abstraction (Lecture 01, Era 3/5) applied to code we actually wrote, not left as slideware.

## Non-negotiables — automatic deductions (§5.3, verbatim)

- A .env, key, token or password anywhere in Git history — −20, plus you must rotate the credential and write an incident note
- An LLM API key in a committed Kubernetes manifest, even base64-encoded (base64 is encoding, not encryption) — −15
- Unpinned base image, or postgres / redis / node without a tag — −8
- localhost used for service-to-service communication — −8
- Frontend able to reach the database — network segmentation not implemented — −8
- Published database or cache port in compose.prod.yaml, or a NodePort/LoadBalancer Service on the database — −8
- Publishing or deploying job not gated by needs: — −8
- Deploying :latest anywhere — −8
- PostgreSQL as a Deployment with no PVC — −8
- Commits pushed directly to main — −5
- README quickstart that does not work from a clean clone — −5

Check every one of these before any commit touching secrets, images, networking, or CI/CD — they are hard constraints to prevent, not defects to catch in review afterward.

## Workflow contract

- Work happens in phases. Each phase gets a written spec first; I approve it before any code is written for that phase.
- Do not start a new phase until I explicitly say so — finishing one phase is not implicit permission to begin the next.
- If the spec, or the assignment text, is ambiguous or underspecified, stop and ask. Do not guess and proceed — a wrong assumption compounds across every phase built on top of it.
- No dependencies, scaffolding, or code beyond an approved phase's stated scope.

## Solo-first, partner-ready

There is a real 2-person team on paper; my partner is not currently active and is expected to join later. I'm working solo until then, and the project must work either way without rework. In practice:

- Keep the four backend layers, and the frontend/backend/infra boundary, genuinely clean — not just labeled. Each natural module (frontend, backend AI/triage layer, backend CRUD/API layer, k8s manifests, CI/CD) must be handable to a second person as a self-contained task without them needing to touch code outside it.
- Every cross-module boundary is exactly the contract recorded in `docs/CONTRACTS.md` — the API table, the DB schema, the `TriageProvider` interface, the cache/rate-limit behaviour. Changing one of those is a decision to flag, never a side-effect of an unrelated change.
- `docs/PARALLEL-WORK-PLAN.md` is the draft list of task slices to hand to my partner when he joins, with what each depends on and which interface it must respect.
- Category A (collaboration, 15 marks) contains line items that need a real, sustained second contributor — partner PR reviews, a commit-share floor, a genuine two-author merge conflict. Deciding "he'll join later" doesn't manufacture that history retroactively; these stay tracked as risk in `docs/RUBRIC-CHECKLIST.md` until he's actually contributing.

## Tech stack

**Fixed by the spec — do not relitigate:**
- Frontend: React 18 + Vite + TypeScript, multi-stage build, served by nginx:alpine
- Backend: FastAPI + Pydantic v2 (recommended) or Flask (permitted, must be declared in README)
- Database: PostgreSQL 16, schema managed by Alembic migrations only — no DDL in app startup
- Cache: Redis 7, doing two jobs — read-through stats cache and a distributed rate limiter
- AI layer: `TriageProvider` interface, ≥3 working implementations, selected by `TRIAGE_PROVIDER` env var (LLMTriage, OllamaTriage, RuleBasedTriage; SimulatedTriage required for CI determinism)
- LLM provider: Google Gemini API, model `gemini-3.1-flash-lite`
- Containers: two multi-stage Docker images, non-root, pinned base images, healthchecked
- Orchestration: local Kubernetes cluster (k3d or kind), manifests via Kustomize (base + overlays/dev, overlays/prod) — or Helm, with an ADR justifying the choice
- CI/CD: GitHub Actions — ci.yml, cd.yml, release.yml — images published to GHCR with an SBOM via Syft
- Load testing tool: k6 or hey

**Still open — see `docs/OPEN-DECISIONS.md`, do not decide without me:**
- FastAPI vs Flask
- Kustomize vs Helm
- k3d vs kind
- PII handling stance for Gemini specifically (redact / send-as-is / accept-and-document)
- Repository/product name (spec explicitly permits renaming CivicPulse)
- Rate-limiter algorithm (fixed-window vs token-bucket)
- Load-test tool choice, and which bonus items (if any) to pursue

**Resolved:** LLM provider is Gemini (`gemini-3.1-flash-lite`); scope is the full assignment, self-paced, not the "split into two assignments" hedge (see `docs/OPEN-DECISIONS.md` §9).
