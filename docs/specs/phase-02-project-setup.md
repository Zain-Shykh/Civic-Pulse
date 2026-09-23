Status: backfilled retroactively — this spec was originally given as a
chat instruction and executed before this file existed. Content below is
reproduced verbatim from that instruction, not reconstructed from the
resulting code. See commit history and docs/RUBRIC-CHECKLIST.md for what
was actually delivered against it.

Process note: this phase predates `docs/WORKFLOW.md` and was backfilled rather than committed first.

## Spec (as given)

Close out remaining open decisions and begin Phase 2 (project setup —
tooling and a walking skeleton, still no business logic).

Part A — close decisions:
Update docs/OPEN-DECISIONS.md: mark rate-limiter algorithm as DECIDED
(fixed-window — simple INCR+EXPIRE in Redis, chosen because the requirement
is quota protection, not traffic smoothing, and it's easier to test
deterministically than a Lua-scripted token bucket) and load-test tool as
DECIDED (k6 — matches the repo's own load/k6-script.js path and supports
ramping virtual users, needed to produce the replicas-vs-load chart the
rubric requires). Product name confirmed as CivicPulse, no change needed.
Bonus scope (§4) remains open — leave it, revisit before the CI/CD phase.

Part B — backend project setup:
- backend/pyproject.toml: FastAPI, Pydantic v2, SQLAlchemy, Alembic,
  psycopg (async driver), redis-py, an OpenAI-compatible or native Gemini
  client, pytest + pytest-cov, ruff, mypy — all version-pinned, not "latest"
- Folder structure exactly per docs/CONTRACTS.md and §5.7: app/{routes,
  services,repositories,providers}/, app/providers/triage/{base,llm,ollama,
  rules,simulated,factory}.py as stub files (docstring + `pass` only — no
  triage logic yet, that's a later phase with its own spec)
- alembic/ initialized (env.py configured for the DB URL from environment),
  but ZERO migrations yet — schema arrives in the Data Layer phase
- backend/Dockerfile: python:3.12-slim, multi-stage (builder installs deps,
  final stage copies only what's needed), non-root USER, exec-form CMD,
  HEALTHCHECK against /health, requirements/deps copied before source for
  layer caching. backend/.dockerignore per the required exclusion list.
- A minimal walking-skeleton only: GET /health (always 200, touches
  nothing) and GET /ready (checks Postgres + Redis reachability, 503 naming
  the failed dependency if either is down) — enough to prove the container,
  compose healthchecks, and network segmentation actually work end to end.
  No other routes, no services, no repositories yet.

Part C — frontend project setup:
- frontend/: Vite + React 18 + TypeScript scaffold, package.json pinned
  (not caret ranges you haven't checked), src/{components,pages,api}/
- frontend/Dockerfile: node:22-alpine build stage → nginx:1.27-alpine serve
  stage, final image contains no Node/node_modules/source
- nginx.conf implementing ADR 0002's decision (proxy /api to the backend
  service, so no absolute backend URL is ever baked into the JS bundle)
- frontend/.dockerignore per the required exclusion list
- One placeholder page that renders "CivicPulse — under construction" —
  nothing else, no real Submit/Dashboard/Stats views yet

Part D — Compose walking skeleton:
- compose.yaml (dev): two networks (edge, internal — internal: true),
  frontend on edge only, backend on both, postgres+redis on internal only.
  Three named volumes (pgdata, redisdata, ollama_models placeholder even if
  Ollama isn't wired up yet). Healthchecks on every service,
  depends_on: condition: service_healthy. All credentials via ${...} from
  .env. Dev-only bind mount for backend hot reload.
- compose.prod.yaml: same shape, image: ${IMAGE_TAG} instead of build:, no
  build key anywhere, no published ports on postgres/redis.
- .env.example committed with placeholder values for every variable
  referenced; confirm .env itself is gitignored (it already should be).
- Actually run `docker compose up` yourself and confirm: all containers
  reach healthy, GET /health and /ready both respond correctly, and
  `docker compose exec frontend ping database` FAILS as designed. Report
  the actual output of that ping command — this is a graded proof point
  (§5.3 automatic deduction if network segmentation isn't real) so don't
  just claim it, show the command output.

Part E — bookkeeping:
Update docs/RUBRIC-CHECKLIST.md's evidence column for anything now
genuinely satisfied (pinned images, .dockerignore present, network
segmentation proven, healthchecks present) — leave anything not yet true
as blank, don't mark it done optimistically.

Report back: what you built, the actual docker compose up output summary,
the ping-from-frontend-to-database result specifically, and any ambiguity
you hit. Then stop — do not write any business logic (triage, repositories,
state machine) until I've reviewed this and we spec Phase 3 together.
