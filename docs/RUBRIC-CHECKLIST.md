# Rubric Checklist (§4 + §5.3)

One row per scored line. `[ ]` unchecked / `[x]` done. Evidence/file column starts empty — fill in as work lands. This file should stay in sync with reality; an unchecked box at submission time is cheaper than a checked box that isn't actually true.

## A · Collaboration and version control — 15

Team status: a specific person will probably join, but he has not started and there is no confirmed date. That status does **not** de-risk the lines below — a partner who joins with little runway left cannot retroactively produce weeks of review/commit/conflict history, so these stay AT RISK regardless of whether he eventually joins.

| Done | Item | Marks | Evidence/file | Partner dependency |
|---|---|---|---|---|
| [ ] | main protected: no direct push, PR required, CI required, ≥1 approval; screenshot in docs/evidence/ | 3 | | Needs the partner active to approve PRs (or an instructor exception) |
| [ ] | Two-branch model with dev plus feature branches; no work committed directly to main | 2 | | Achievable solo |
| [ ] | ≥5 merged PRs, each linked to an Issue, each with a substantive review comment from your partner | 4 | | **AT RISK regardless of eventual joining** — needs him actively reviewing across several PRs, not a one-time favor at the end |
| [ ] | ≥35 commits, conventional prefixes (feat:, fix:, docs:…), neither partner below 35% by `git shortlog -sn` | 3 | | **AT RISK regardless of eventual joining** — the 35%-floor needs a real, sustained share of commits; a late joiner cannot hit 35% without either a large late push or the total commit count staying artificially low |
| [ ] | One deliberate merge conflict on real code, resolved, with markers/resolution/merge evidence and 2–4 sentences on why that version won | 3 | | **AT RISK regardless of eventual joining** — needs two divergent branches from two real contributors working concurrently; not producible in a single late session |

**Category A total at risk: up to 10/15 marks, unresolved.** Recorded in `docs/OPEN-DECISIONS.md` §9. Do not mark these as "will be fine, partner is coming" — with no confirmed join date, plan as if they may not be earned, and treat any actual early contribution from him as upside, not the baseline plan.

## B · Frontend — 18

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [ ] | Submit view: validation, honest loading state, renders category, priority, AI summary and provider | 5 | |
| [ ] | Dashboard: pagination, filters, status transitions, server's 409 message surfaced verbatim | 5 | |
| [ ] | Stats view rendering aggregates and cache-hit state from X-Cache | 3 | |
| [ ] | Runtime configuration — no baked-in API URL; one image runs in any environment | 3 | |
| [ ] | ≥5 meaningful component tests passing in CI | 2 | |

## C · Backend — 25

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [ ] | All nine endpoints to contract, correct status codes, field-level validation errors (rubric says "ten," confirmed typo — see `docs/CONTRACTS.md`) | 7 | |
| [ ] | Four-layer separation: no SQL outside repositories, no business rules in routes | 4 | |
| [ ] | Status state machine as an explicit transition table; invalid transitions 409 | 3 | |
| [x] | /health and /ready correctly distinguished; /health does not touch the database | 3 | `backend/app/routes/health.py`; verified live 2026-09-19: `docker compose exec backend` → GET /health 200 always, GET /ready 200 when Postgres+Redis reachable; `backend/tests/test_health.py` covers the 503-naming-failed-dependency branch |
| [ ] | Structured JSON logging to stdout with a propagated request_id | 3 | |
| [ ] | SIGTERM handled: in-flight requests drain before exit | 2 | |
| [ ] | ≥14 backend tests, unit and integration, deterministic, coverage ≥65% | 3 | |

## D · Data layer — 12

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [x] | Alembic migrations; zero schema DDL in application startup code | 4 | `backend/alembic/versions/be5a6b3416a1_create_complaints_table.py`; verified 2026-09-20: `alembic upgrade head` succeeds against real Postgres 16, `alembic downgrade base` then `upgrade head` again is clean (genuinely reversible, not forward-only). No `CREATE TABLE` anywhere in `app/`. |
| [x] | Schema complete including triaged_by, ai_summary, triage_latency_ms, timestamptz | 3 | Same migration file. Verified against live DB via `\d complaints` (psql) — every column, type, default, and nullability matches `docs/CONTRACTS.md` §2.3 / `docs/architecture/SCHEMA.md` field-for-field. |
| [x] | Two indexes, each justified by a named query in your notes | 2 | `ix_complaints_status_priority`, `ix_complaints_created_at`, justified per-query in `docs/architecture/SCHEMA.md` ("Indexes" section). Verified present via `pg_indexes` against live DB. |
| [x] | Idempotent seed of ≥30 realistic complaints; running it twice changes nothing | 3 | `backend/app/scripts/seed.py` — 36 complaints, Urdu-influenced English, spread across all 6 categories/3 priorities/4 statuses. Verified live: first run inserted 36 rows, second run inserted 0 (36 already present). |

## E · Cache layer — 10

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [ ] | /api/stats read-through cache, 30 s TTL, correct X-Cache header | 3 | |
| [ ] | Cache invalidated on write, not left to expire | 2 | |
| [ ] | Distributed Redis rate limiter on POST /api/complaints, 429 with Retry-After | 4 | |
| [ ] | Redis AOF on a named volume, with your justification written down | 1 | |

## F · AI layer — 25

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [ ] | TriageProvider interface with ≥3 working implementations selected by environment variable | 5 | |
| [ ] | Structured output requested and validated against a Pydantic schema; malformed output rejected safely | 5 | |
| [ ] | Timeout, single jittered retry on retryable errors only, fallback to rules, triaged_by recorded | 6 | |
| [ ] | Content-hash caching of triage results with a measured, reported hit rate | 3 | |
| [ ] | Prompt-injection guardrail plus a test that submits an injection attempt | 3 | |
| [ ] | triage_latency_ms recorded and surfaced through /api/meta/providers | 2 | |
| [ ] | PII/data-governance ADR: what leaves your machine, to whom, and why that is acceptable | 1 | |

## G · Docker and Compose — 15

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [x] | Both images multi-stage, pinned base, non-root USER, exec-form CMD, cache-correct layer order | 4 | `backend/Dockerfile` (python:3.12-slim, USER civicpulse), `frontend/Dockerfile` (node:22-alpine → nginx:1.27-alpine, USER nginx); both built successfully 2026-09-19 |
| [x] | .dockerignore per build context, with before/after context sizes reported | 2 | `backend/.dockerignore`, `frontend/.dockerignore`. Measured 2026-09-19: raw dir size before exclusions ≈ 23 MB (backend, incl. local `.mypy_cache`/`.pytest_cache`) and ≈ 120 MB (frontend, incl. `node_modules`); actual BuildKit context transferred after `.dockerignore` ≈ 2.9 kB combined across both images (`docker compose build --no-cache --progress=plain`) |
| [x] | Two networks with internal: true; frontend provably cannot reach the database | 4 | `compose.yaml`. Verified live 2026-09-19: `docker compose exec frontend ping -c 3 postgres` → `ping: bad address 'postgres'`, exit code 1 (DNS resolution fails — frontend isn't on `internal`) |
| [x] | Three named volumes, each justified; dev bind mount present and absent from prod | 2 | `compose.yaml` (pgdata, redisdata, ollama_models + dev bind mount `./backend/app:/app/app:ro`), `compose.prod.yaml` (same three volumes, no bind mount) |
| [x] | Healthchecks on all services with depends_on: condition: service_healthy | 2 | `compose.yaml`; verified live 2026-09-19: all four containers (`frontend`, `backend`, `postgres`, `redis`) reached `Healthy` via `docker compose up -d` / `docker compose ps` |
| [x] | compose.prod.yaml uses image: ${IMAGE_TAG}, no build:, no published DB or cache port | 1 | `compose.prod.yaml`; verified via `docker compose -f compose.prod.yaml config` — no `build:` key, no ports on `postgres`/`redis` |

## H · Kubernetes — 20

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [ ] | Namespace, Deployments, StatefulSet + PVC for Postgres, ClusterIP Services, Ingress routing / and /api | 5 | |
| [ ] | ConfigMap and Secret separated; committed manifests carry placeholders only | 2 | |
| [ ] | All three probes correct: liveness independent of the database, readiness dependent on it | 4 | |
| [ ] | resources.requests and limits set on every container | 2 | |
| [ ] | HPA v2 with tuned behavior, plus captured `kubectl get hpa -w` output and a replicas-vs-load chart from a real load test | 4 | |
| [ ] | VPA in recommender mode, recommendations committed, requests updated in response, HPA/VPA conflict explained | 3 | |

## I · CI/CD — 20

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [ ] | ci.yml running lint, type check, backend and frontend tests on every PR, configured as required checks | 4 | |
| [ ] | Compose integration smoke job asserting a real request path end to end | 3 | |
| [ ] | Trivy image scan and kubeconform manifest validation in CI | 3 | |
| [ ] | cd.yml with needs: gating publish, images pushed to GHCR tagged by commit SHA | 4 | |
| [ ] | Kubernetes deploy job on an ephemeral cluster, waiting on rollout status and smoke-testing the Ingress | 3 | |
| [ ] | Secrets from GitHub Secrets with a scoped token and a least-privilege permissions: block | 2 | |
| [ ] | Evidence of a red pipeline blocking a merge, then green | 1 | |

## J · Documentation, portfolio and reflection — 15

| Done | Item | Marks | Evidence/file | Partner dependency |
|---|---|---|---|---|
| [ ] | README.md: problem statement, badges, Mermaid architecture diagram, working one-command quickstart, API table, screenshots | 4 | | |
| [ ] | Four ADRs: provider interface; frontend runtime config; deploy-by-SHA; PII/data governance | 4 | | |
| [ ] | docs/RUNBOOK.md: how to deploy, roll back, read logs, and what to do when triage starts failing | 2 | | |
| [ ] | Demo video ≤5 minutes, both partners speaking, covering clean clone → running system, AI triage, fallback, network isolation failing, HPA scaling, rollback | 3 | | **AT RISK regardless of eventual joining** — needs him actually present and speaking by recording time, which has no confirmed date |
| [ ] | docs/ENGINEERING-NOTES.md answering all eight questions in §5.2 with file-and-line references | 2 | | |

## Bonus — capped at +15

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [ ] | Zero-downtime rolling update demonstrated under live load with zero failed requests | +4 | |
| [ ] | GitOps: Argo CD or Flux reconciling the cluster from the repository | +4 | |
| [ ] | Deploy by image digest rather than tag, with Cosign signing and verification in CI | +3 | |
| [ ] | Prometheus scraping /metrics plus a Grafana dashboard, screenshot committed | +2 | |
| [ ] | OpenTelemetry tracing across frontend → backend → LLM call | +2 | |

## §5.3 Automatic deductions — checklist to *avoid*, not earn

| Done | Item | Penalty | Evidence/file |
|---|---|---|---|
| [x] | No .env, key, token or password anywhere in Git history | −20 | Verified 2026-09-19: `.env` confirmed gitignored (`git check-ignore -v .env`), never staged. Ongoing invariant — re-check before every commit, not a one-time fact |
| [ ] | No LLM API key in a committed Kubernetes manifest (base64 included) | −15 | No k8s manifests exist yet |
| [x] | No unpinned base image; postgres / redis / node all tagged | −8 | `python:3.12-slim`, `node:22-alpine`, `nginx:1.27-alpine`, `postgres:16-alpine`, `redis:7-alpine` — every image tag pinned, none `latest` |
| [x] | No localhost used for service-to-service communication | −8 | `compose.yaml`/`compose.prod.yaml` use service DNS names (`postgres`, `redis`, `backend`) throughout — no `localhost`/`127.0.0.1` between containers |
| [x] | Frontend cannot reach the database (network segmentation proven) | −8 | Same live proof as the G-category network row above: `ping postgres` from `frontend` fails with `bad address` |
| [x] | No published database or cache port in compose.prod.yaml; no NodePort/LoadBalancer on the database | −8 | Compose portion verified (no ports on postgres/redis in `compose.prod.yaml`). K8s portion (NodePort/LoadBalancer) not yet applicable — no manifests exist yet |
| [ ] | Every publishing/deploying job gated by needs: | −8 | No CI/CD workflows exist yet |
| [x] | :latest never deployed anywhere | −8 | `compose.prod.yaml` deploys `${IMAGE_TAG}` only; see `docs/adr/0003-deploy-by-sha.md` |
| [ ] | PostgreSQL never a bare Deployment with no PVC | −8 | No k8s manifests exist yet |
| [x] | No commits pushed directly to main | −5 | All work committed on `dev`; `main` untouched since the Phase 0 initial commit |
| [ ] | README quickstart verified to work from a clean clone | −5 | README is still a stub — no quickstart written yet |
