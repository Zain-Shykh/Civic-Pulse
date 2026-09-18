# Rubric Checklist (§4 + §5.3)

One row per scored line. `[ ]` unchecked / `[x]` done. Evidence/file column starts empty — fill in as work lands. This file should stay in sync with reality; an unchecked box at submission time is cheaper than a checked box that isn't actually true.

## A · Collaboration and version control — 15

| Done | Item | Marks | Evidence/file | Partner dependency |
|---|---|---|---|---|
| [ ] | main protected: no direct push, PR required, CI required, ≥1 approval; screenshot in docs/evidence/ | 3 | | Needs the partner active to approve PRs (or an instructor exception) |
| [ ] | Two-branch model with dev plus feature branches; no work committed directly to main | 2 | | Achievable solo |
| [ ] | ≥5 merged PRs, each linked to an Issue, each with a substantive review comment from your partner | 4 | | **Needs the partner actively reviewing** — at risk until he's onboarded |
| [ ] | ≥35 commits, conventional prefixes (feat:, fix:, docs:…), neither partner below 35% by `git shortlog -sn` | 3 | | **Needs the partner contributing a real share** — the 35%-floor is unearnable if he joins too late to accumulate commits |
| [ ] | One deliberate merge conflict on real code, resolved, with markers/resolution/merge evidence and 2–4 sentences on why that version won | 3 | | **Needs two divergent branches from two real contributors** — plan a task slice (see `docs/PARALLEL-WORK-PLAN.md`) that naturally overlaps with mine once he's on board |

**Category A total at risk while the partner is inactive: up to 10/15 marks.** Decision recorded in `docs/OPEN-DECISIONS.md` §9: he's expected to join later and pick up slices from `docs/PARALLEL-WORK-PLAN.md`. Residual risk is timing, not whether he exists — if he joins late, these items must be compressed into whatever time remains.

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
| [ ] | /health and /ready correctly distinguished; /health does not touch the database | 3 | |
| [ ] | Structured JSON logging to stdout with a propagated request_id | 3 | |
| [ ] | SIGTERM handled: in-flight requests drain before exit | 2 | |
| [ ] | ≥14 backend tests, unit and integration, deterministic, coverage ≥65% | 3 | |

## D · Data layer — 12

| Done | Item | Marks | Evidence/file |
|---|---|---|---|
| [ ] | Alembic migrations; zero schema DDL in application startup code | 4 | |
| [ ] | Schema complete including triaged_by, ai_summary, triage_latency_ms, timestamptz | 3 | |
| [ ] | Two indexes, each justified by a named query in your notes | 2 | |
| [ ] | Idempotent seed of ≥30 realistic complaints; running it twice changes nothing | 3 | |

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
| [ ] | Both images multi-stage, pinned base, non-root USER, exec-form CMD, cache-correct layer order | 4 | |
| [ ] | .dockerignore per build context, with before/after context sizes reported | 2 | |
| [ ] | Two networks with internal: true; frontend provably cannot reach the database | 4 | |
| [ ] | Three named volumes, each justified; dev bind mount present and absent from prod | 2 | |
| [ ] | Healthchecks on all services with depends_on: condition: service_healthy | 2 | |
| [ ] | compose.prod.yaml uses image: ${IMAGE_TAG}, no build:, no published DB or cache port | 1 | |

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
| [ ] | Demo video ≤5 minutes, both partners speaking, covering clean clone → running system, AI triage, fallback, network isolation failing, HPA scaling, rollback | 3 | | **"Both partners speaking" needs the partner on board by recording time** |
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
| [ ] | No .env, key, token or password anywhere in Git history | −20 | |
| [ ] | No LLM API key in a committed Kubernetes manifest (base64 included) | −15 | |
| [ ] | No unpinned base image; postgres / redis / node all tagged | −8 | |
| [ ] | No localhost used for service-to-service communication | −8 | |
| [ ] | Frontend cannot reach the database (network segmentation proven) | −8 | |
| [ ] | No published database or cache port in compose.prod.yaml; no NodePort/LoadBalancer on the database | −8 | |
| [ ] | Every publishing/deploying job gated by needs: | −8 | |
| [ ] | :latest never deployed anywhere | −8 | |
| [ ] | PostgreSQL never a bare Deployment with no PVC | −8 | |
| [ ] | No commits pushed directly to main | −5 | |
| [ ] | README quickstart verified to work from a clean clone | −5 | |
