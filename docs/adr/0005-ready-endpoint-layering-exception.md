# ADR 0005: `/ready`'s direct infra probe is a scoped exception to the four-layer rule

## Status

Accepted

## Context

`CLAUDE.md`'s four-layer rule is a hard constraint: `routes/` → `services/` → `repositories/` → `providers/`, one direction only, and "a route that opens a database session is a design failure worth marks."

Phase 2 (`backend/app/routes/health.py`) implemented `GET /health` and `GET /ready` as the walking skeleton, before any `services/` or `repositories/` content exists. `/ready` must report 503 naming whichever of Postgres/Redis is unreachable. As written, the route calls `app.db.ping()` and `app.providers.cache.ping()` directly — bypassing `services/` and `repositories/` entirely, because neither layer has any content yet to route through.

This is a real deviation from the stated rule, not an oversight — it needs a decision on record rather than silently becoming the pattern every future route copies.

## Decision

`/health` and `/ready` are liveness/readiness probes, not domain queries — they answer "is this process able to serve traffic," not "what is true about a complaint." A `repositories/` module exists to encapsulate domain persistence (complaint CRUD, filtering, stats aggregation) behind methods that hide SQL from callers; routing a raw TCP/protocol-level connectivity check through that abstraction would add a layer of indirection with no purpose, since there's no domain query to hide.

`/ready` therefore calls `app/db.py::ping()` (a bare `SELECT 1`-equivalent connectivity check, not a repository) and `app/providers/cache.py::ping()` (a legitimate `providers/` call — Redis connectivity is exactly what a provider module is for) directly from the route.

**Scope of the exception — read literally, not as precedent:**

- Applies **only** to `GET /health` and `GET /ready`.
- Applies **only** to raw reachability checks (can we open a connection / get a PONG). The moment a check needs to know anything about complaints, categories, or any other domain concept, that logic belongs in `services/`+`repositories/` like everything else — no exception.
- Any future route that queries or mutates domain data goes through `services/` → `repositories/` with **no exceptions**, regardless of how small the query looks.

## Consequences

- `app/db.py` stays intentionally thin — a connection ping, not a repository. It must never grow query methods; the moment it needs one, that method belongs in `repositories/` instead, and `db.py` goes back to being infrastructure-only (engine/session setup).
- A reviewer (or a joining partner) skimming `routes/` will see exactly one file that talks to infra directly, with this ADR linked from its docstring — the exception is visible at the point it's taken, not just written down here.
- `CLAUDE.md` cross-references this ADR next to the four-layer rule so the rule's own statement doesn't read as violated-and-unexplained.

## Alternatives considered

- **A `HealthRepository`/`HealthService` wrapping the same two calls:** rejected — it satisfies the letter of the four-layer rule while adding two files whose only job is to immediately call `db.ping()`/`cache.ping()` with no business rule in between. Indirection that hides nothing is the thing the rule exists to prevent, not honor.
- **Deferring `/health`/`/ready` until `services/`/`repositories/` exist:** rejected — Phase 2's entire point was proving the container/compose/network setup works end-to-end before any business logic is written; that proof needs a real readiness check now, not later.
