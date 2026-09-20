# Phase 06: Service layer
Status: done
Depends on: Phase 4 (repositories — `backend/app/repositories/complaints.py`), Phase 5a (RuleBasedTriage + SimulatedTriage — the minimum IMPLEMENTATION-PLAN.md names for this phase; Phase 5b/LLMTriage is also already done and usable, but not required by this phase)
Reads first: `docs/CONTRACTS.md` (§2.2 status state machine, §2.5 TriageProvider/engineering requirements 1–7, mandatory Determinism test), `docs/adr/0001-provider-interface.md`, `docs/IMPLEMENTATION-PLAN.md` (Phase 6 section), `backend/app/repositories/complaints.py`, `backend/app/providers/triage/factory.py`, `backend/app/providers/triage/base.py`, `backend/app/providers/triage/simulated.py`

## Goal
Build the `services/` layer that sits between the (not-yet-built) routes and the repository/provider layers: it is the first place in the codebase that enforces the complaint status state machine (the repository currently writes any status verbatim, by explicit design — see that module's docstring) and the first place that actually calls a `TriageProvider` in an orchestration flow (persist the triaged result, time the call, and — critically — provide the fallback safety net the mandatory Determinism test requires, since not every provider implements that safety net itself).

## Deliverables

**`backend/app/services/complaints.py`**
- An explicit transition table (dict/set of `(from_status, to_status)` pairs), not a chain of `if`s, per `docs/CONTRACTS.md` §2.2's literal instruction. Legal transitions: `open→in_progress`, `in_progress→resolved`, `open→rejected`, `in_progress→rejected`. `resolved` and `rejected` are terminal — no transition out of either is legal.
- `change_status(complaint_id, new_status)`: reads the complaint's current status (via `repositories.complaints.get_by_id`), checks it against the transition table, and either calls `repositories.complaints.update_status(...)` on success or raises `IllegalTransitionError` (see below) — this is the enforcement point IMPLEMENTATION-PLAN.md's Phase 6 bullet names explicitly ("Status state machine ... 409 on invalid ones"), and the one Phase 4's own docstring pointed to as *this* phase's job, not the repository's.
- `submit_complaint(provider, *, text, location, reporter_contact)`: the triage-orchestration function.
  - Times the call (`time.monotonic()` before/after) to populate `triage_latency_ms` — required by the schema (`docs/CONTRACTS.md` §2.3) and only measurable here, since it spans exactly one `provider.triage()` call.
  - Calls `await provider.triage(text, location)` **wrapped in a bare `except Exception` that falls back to a fresh `RuleBasedTriage()` instance and overwrites `triaged_by` to the literal string `"rules:fallback"`** — deliberately not trusting individual providers to guarantee this themselves. See "Why the service layer needs its own fallback wrap" below; this is the answer to the Plan-stage question about whether this duplicates LLMTriage's own retry/fallback engineering.
  - Persists the result via `repositories.complaints.create(...)`, passing through `category`/`priority`/`summary`(as `ai_summary`)/`confidence`(dropped — not a DB column)/`triaged_by`/the measured `triage_latency_ms`, plus the caller-supplied `text`/`location`/`reporter_contact`.
  - Returns the created row (same dict shape `repositories.complaints.create` returns).
- `get_stats()`: thin wrapper over `repositories.complaints.stats_summary()`. No caching, no `X-Cache` header (Phase 8). Whether any field renaming/shaping belongs here beyond a passthrough has no citable source yet — see Open Questions.

**`backend/app/services/exceptions.py`**
- `IllegalTransitionError(Exception)`, carrying `current_status` and `attempted_status` attributes. `docs/CONTRACTS.md` only specifies the eventual HTTP-level behaviour ("409 naming the attempted transition"); no route layer exists yet to produce that response. This exception is the seam: it carries exactly the two facts Phase 7 will need to build that 409 body, without the service layer knowing anything about HTTP status codes or response shapes.

**`backend/tests/test_services_complaints.py`**
- State machine: one test per legal transition (succeeds, row's `status` updated); a representative set of illegal transitions — both terminal states attempting any further transition, and the two non-adjacent jumps (`open→resolved` directly, `in_progress→open` backwards) — each asserting `IllegalTransitionError` is raised with the correct `current_status`/`attempted_status`.
- Triage orchestration: `submit_complaint()` with `SimulatedTriage()` round-trips into a real row (`triaged_by == "simulated"`, `triage_latency_ms > 0`, all other fields present); a second case using `RuleBasedTriage()` directly as the primary provider.
- **Mandatory Determinism test** (`docs/CONTRACTS.md` §2.5: *"Write this test if you write no other: given a provider that always raises, POST /api/complaints still returns 201 and triaged_by == 'rules:fallback'."*) — exercised here at the service level since routes don't exist yet, same precedent Phase 5a/5b already established: `submit_complaint(SimulatedTriage(always_raise=True), ...)` must still return a persisted row with `triaged_by == "rules:fallback"`, not raise.
- `get_stats()`: at least one test against the real seeded DB confirming the counts match `_COMPLAINTS`' known distribution (same style as `test_repositories.py`'s existing stats-adjacent checks, if any — otherwise a fresh assertion against `app.scripts.seed._COMPLAINTS`).
- No mocks, no fixtures file: tests connect to the real Postgres via `app.db.engine`, same pattern `test_repositories.py`/`test_schema.py` already established (precondition: `alembic upgrade head` + seed already run; any row a test inserts itself is cleaned up in a `finally`). No `conftest.py` exists yet and none is introduced by this phase — nothing here needs one.

### Why the service layer needs its own fallback wrap
This was flagged in the assignment prompt for this spec as a real decision, not a formality, and it resolves to a concrete, citable answer rather than a judgment call:

`SimulatedTriage.triage()` (`backend/app/providers/triage/simulated.py`), when constructed with `always_raise=True`, raises `RuntimeError` **uncaught** — it has no internal fallback of its own (confirmed by reading the class and by the existing test `test_simulated_triage_always_raise`, which asserts the raise propagates). `docs/CONTRACTS.md`'s CI determinism requirement pins CI to exactly this provider. The mandatory Determinism test's wording ("given a provider that always raises...") is provider-agnostic, not scoped to `LLMTriage`. Since the one CI-pinned provider that can be configured to raise has no built-in fallback, **the fallback safety net cannot live only inside `LLMTriage`** (where it already exists, per Phase 5b) — it must also exist one layer up, in the orchestration function that calls whichever provider the factory/caller hands it. So: no, the service layer does not need to duplicate `LLMTriage`'s own timeout/retry engineering (requirements 2–3 stay owned by the provider that makes the network call) — but yes, it needs its own catch-all exception-to-fallback wrap, because that specific piece (requirement 4, "fall back on exhausted retries") is the one piece that isn't universally guaranteed by every provider individually, and the mandatory test requires it to hold for *any* provider.

## Non-goals
- No routes, no FastAPI wiring, no HTTP status codes or response bodies — the exact 409/404 JSON shapes are Phase 7's job. `IllegalTransitionError` only carries the data Phase 7 will need.
- No Redis caching of `/api/stats`, no `X-Cache` header — Phase 8.
- No content-hash triage-result caching (`docs/CONTRACTS.md` §2.5 requirement 5) — already deferred to Phase 8 by `llm.py`'s own docstring; this phase doesn't reopen it.
- No `OllamaTriage` — unscheduled, unrelated to this phase (`docs/specs/phase-05b-llm-triage.md`'s Open Question 1, still unresolved).
- No decision about *how* a route will eventually obtain a `TriageProvider` instance (per-request vs. a startup-time singleton via FastAPI `Depends`) — see Open Questions. This phase sidesteps needing an answer by having `submit_complaint()` take the provider as an explicit parameter rather than calling `get_triage_provider()` itself.

## Open Questions
1. **Provider lifecycle (construction frequency).** `docs/adr/0001-provider-interface.md` says a provider is "obtained once from the factory (e.g. via FastAPI dependency injection)" but doesn't say once *per process* (a startup-time singleton reused across all requests) or once *per request* (the factory called fresh each time, but only once within that request). This matters concretely for `LLMTriage`, whose `__init__` constructs a `genai.Client` — real, possibly non-trivial cost to build per-request, and no source states whether `genai.Client`/its underlying `httpx.AsyncClient` is safe to share across concurrent requests. `services/` can't answer this on its own since no FastAPI app or route exists yet to wire `Depends()` into (this phase's own "Done looks like" bar is explicitly "no FastAPI involved yet"). Proposed resolution for *this* phase: `submit_complaint()` takes `provider: TriageProvider` as a required parameter, so the lifecycle question is fully deferred to whichever Phase 7 code eventually calls `get_triage_provider()` and wires it into a route. Flagging for a decision before or during Phase 7, not blocking Phase 6.
2. **`get_stats()` output shape.** `docs/CONTRACTS.md` §2.2 only says `GET /api/stats` returns "aggregates" — no committed JSON shape exists yet (the repository's own docstring explicitly punts the response shape to "Service/route concerns for a later phase"). Is a straight passthrough of `repositories.complaints.stats_summary()`'s dict (`counts_by_status`, `counts_by_category`, `average_triage_latency_ms`) acceptable as this phase's `get_stats()`, or should some renaming/reshaping happen now speculatively ahead of Phase 7's response models? No citable source pins this either way.
3. **`change_status()` on a missing complaint ID.** `repositories.complaints.update_status()` returns `None` if the ID doesn't exist (not an exception). Should the service raise a typed `NotFoundError` (mirroring `IllegalTransitionError`'s pattern) or simply propagate `None` for Phase 7 to turn into a 404, the same way `get_by_id`'s `None` already works today? No source specifies this; proposing to propagate `None` (consistent with the repository's own existing not-found convention) unless told otherwise.
4. **Confidence field.** `TriageResult.confidence` has no corresponding column in the `complaints` table schema (`docs/CONTRACTS.md` §2.3's schema table doesn't list one). Confirming it is simply dropped when persisting (used only in-memory / for future observability, per the `/api/meta/providers` "last 20 triage outcomes" surface in Phase 7+) rather than silently lost by oversight — flagging so this isn't a silent decision.

## Verification required
- `docker compose up -d postgres` (or the existing test-DB setup Phase 4 established), `alembic upgrade head`, run the seed script, then run tests inside a container joined to that network — same infra pattern `test_repositories.py`/`test_schema.py` already use, not the bare ad-hoc container Phase 5b used (Phase 5b needed no DB; this phase does).
- `python -m pytest backend/tests/test_services_complaints.py -v -o asyncio_mode=auto`, full output pasted, run twice back-to-back to rule out order-dependency/state leakage between tests (this phase inserts/updates real rows — cleanup discipline must be verified empirically, not assumed).
- Also re-run `backend/tests/test_repositories.py backend/tests/test_triage_providers.py backend/tests/test_llm_triage.py` alongside the new file in the same DB-joined container, to confirm nothing in this phase regresses the existing suites now that they share a real database.
- `ruff check .` and `mypy app` from `backend/`, clean output pasted in full.
- Manual confirmation, pasted: the Mandatory Determinism test's assertion (`triaged_by == "rules:fallback"` when the provider always raises) demonstrated once outside the test runner too (a short ad-hoc script or REPL snippet calling `submit_complaint(SimulatedTriage(always_raise=True), ...)` directly and printing the result) — cite `docs/CONTRACTS.md` §2.5's exact sentence in the As-Built when this is done.

## Ambiguity handling
If anything encountered during Plan drafting conflicts with `docs/CONTRACTS.md`, `docs/adr/0001-provider-interface.md`, or `docs/IMPLEMENTATION-PLAN.md`, or remains underspecified after checking those three, stop and ask — do not silently resolve it in the Plan. The four Open Questions above are exactly that class of thing and are listed for a decision now, not resolved by assumption.

## Plan

### OQ2 (get_stats() shape) — closed, not genuinely open

Re-read `backend/app/repositories/complaints.py:136-161` directly. `stats_summary()` already returns a fully shaped, JSON-serializable dict:

```python
return {
    "counts_by_status": {row.status: row.n for row in by_status},
    "counts_by_category": {row.category: row.n for row in by_category},
    "average_triage_latency_ms": float(avg_latency) if avg_latency is not None else 0.0,
}
```

This is not raw row data — the SQL already groups, the Python already turns rows into `{key: count}` dicts, and `None` (no rows yet) is already normalized to `0.0`. The function's own docstring frames this as "raw aggregate data" with "response shape ... Service/route concerns for a later phase," but that framing is stale relative to what the code actually does — there is no unshaped data left for a later phase to shape. **OQ2 is closed**: `get_stats()` is a true one-line passthrough, nothing added:

```python
async def get_stats() -> dict[str, Any]:
    return await repositories.complaints.stats_summary()
```

If a future phase's route/frontend needs a different key naming or nesting, that's a Phase 7 route-serialization decision (e.g. a Pydantic response model), not a reason to touch this function now.

### OQ3 (missing complaint ID) — proposed resolution, for approval

Proposing `NotFoundError`, same file and same shape pattern as `IllegalTransitionError`:

```python
# backend/app/services/exceptions.py
class IllegalTransitionError(Exception):
    def __init__(self, current_status: str, attempted_status: str) -> None:
        self.current_status = current_status
        self.attempted_status = attempted_status
        super().__init__(f"{current_status} -> {attempted_status} is not a legal transition")


class NotFoundError(Exception):
    def __init__(self, complaint_id: uuid.UUID) -> None:
        self.complaint_id = complaint_id
        super().__init__(f"complaint {complaint_id} not found")
```

`change_status()` raises `NotFoundError(complaint_id)` when `repositories.complaints.get_by_id()` returns `None`, instead of silently propagating `None` as the Spec's Open Question originally floated. Rationale for proposing the typed exception over propagating `None`: `change_status()`'s success path already returns a `dict[str, Any]` (the updated row), so a `None` return would be a third, untyped meaning ("not found") layered onto a function whose two other outcomes are "return a dict" or "raise `IllegalTransitionError`" — inconsistent and easy for a Phase 7 caller to miss with a truthiness check. A typed exception makes both failure modes of `change_status()` symmetric and equally impossible to silently ignore. **This is a proposal, not a decision** — flagging for approval alongside the rest of this Plan.

### Files touched, in order

1. `backend/app/services/exceptions.py` — `IllegalTransitionError`, `NotFoundError` (written first; `complaints.py` imports from it).
2. `backend/app/services/complaints.py` — transition table, `change_status()`, `submit_complaint()`, `get_stats()`.
3. `backend/tests/test_services_complaints.py`.

### The transition table

Per `docs/CONTRACTS.md` §2.2, as an explicit set of legal `(from, to)` pairs — not a chain of `if`s:

```python
_LEGAL_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("open", "in_progress"),
    ("in_progress", "resolved"),
    ("open", "rejected"),
    ("in_progress", "rejected"),
})
```

`resolved` and `rejected` are terminal by construction — they simply never appear as the first element of any tuple, so any transition attempted from either falls straight into the "not in the table" branch, with no special-cased terminal-state check needed.

```python
async def change_status(complaint_id: uuid.UUID, new_status: str) -> dict[str, Any]:
    complaint = await repositories.complaints.get_by_id(complaint_id)
    if complaint is None:
        raise NotFoundError(complaint_id)

    current_status = complaint["status"]
    if (current_status, new_status) not in _LEGAL_TRANSITIONS:
        raise IllegalTransitionError(current_status, new_status)

    updated = await repositories.complaints.update_status(complaint_id, new_status)
    assert updated is not None  # existence just confirmed above; no concurrent-delete handling in scope
    return updated
```

### The fallback wrap — exactly where and what it catches

Found while reviewing the Deliverables, not assumed: it wraps **only the `await provider.triage(text, location)` call itself**, inside `submit_complaint()` — nothing wraps the factory (the factory isn't called here at all; `provider` arrives as a parameter, per OQ1's resolution in the Spec). It catches bare `Exception` (not `BaseException` — `asyncio.CancelledError` is a `BaseException` in the versions of Python this project targets, so cancellation still propagates untouched; no special-casing needed for that). It is deliberately broad rather than scoped to `RuntimeError` (what `SimulatedTriage(always_raise=True)` happens to raise) or to `LLMTriage`'s own exception types, because the mandatory test's wording — "given a provider that always raises" — is provider-agnostic, and a narrower catch would silently stop protecting the very test this exists to satisfy the moment a *different* provider's failure mode raises something else (e.g. a hypothetical `OllamaTriage`'s connection error):

```python
async def submit_complaint(
    provider: TriageProvider, *, text: str, location: str, reporter_contact: str | None
) -> dict[str, Any]:
    start = time.monotonic()
    try:
        result = await provider.triage(text, location)
    except Exception:
        logger.warning("triage_provider_raised_falling_back", extra={"provider": provider.name})
        fallback = await RuleBasedTriage().triage(text, location)
        result = TriageResult(
            category=fallback.category,
            priority=fallback.priority,
            summary=fallback.summary,
            confidence=fallback.confidence,
            triaged_by="rules:fallback",
        )
    triage_latency_ms = int((time.monotonic() - start) * 1000)

    return await repositories.complaints.create(
        complaint_text=text,
        location=location,
        reporter_contact=reporter_contact,
        category=result.category.value,
        priority=result.priority.value,
        ai_summary=result.summary,
        triaged_by=result.triaged_by,
        triage_latency_ms=triage_latency_ms,
    )
```

Note this mirrors `LLMTriage`'s own internal fallback shape exactly (fresh `RuleBasedTriage()` instance, `triaged_by` force-overwritten to the literal `"rules:fallback"` rather than trusting whatever the fallback provider's own `.name` reports) — for `LLMTriage` specifically this outer wrap is a no-op in practice, since `llm.py`'s `triage()` never raises (every code path returns a `TriageResult`, confirmed in Phase 5b's As-Built); the wrap exists for every provider that doesn't already give that guarantee itself.

## As-Built

Implemented exactly as Planned. Three files, in the planned order:
`backend/app/services/exceptions.py`, `backend/app/services/complaints.py`,
`backend/tests/test_services_complaints.py`.

### Deviation from the Plan (one, trivial)

The Plan's `change_status()` sketch put the "no concurrent-delete handling"
comment on the same line as `assert updated is not None`, which ruff's
`E501` (line too long, >100 cols) rejected. Moved the comment to its own
line above the assert — no logic change. This is the only difference
between the Plan's code sketches and what's actually committed.

### Verification — real Postgres, no mocks

Postgres brought up via `docker compose up -d postgres` (network
`assign_1_internal`, container reported `healthy`). Tests ran in an
ephemeral `python:3.12-slim` container with `.[dev]` installed on the
default bridge network (for `pip install` — the `internal` compose network
has no outside route, by design, and pip needs one), then joined to
`assign_1_internal` via `docker network connect` for DB access — so the
project's own network-segmentation deduction line (§5.3) was never
violated to make these tests reachable. `alembic upgrade head` and the
seed script were run first (36 rows already present, idempotent).

**New file alone, run 1:**
```
collected 15 items
tests/test_services_complaints.py::TestStateMachine::test_legal_transitions_succeed[open-in_progress] PASSED
tests/test_services_complaints.py::TestStateMachine::test_legal_transitions_succeed[in_progress-resolved] PASSED
tests/test_services_complaints.py::TestStateMachine::test_legal_transitions_succeed[open-rejected] PASSED
tests/test_services_complaints.py::TestStateMachine::test_legal_transitions_succeed[in_progress-rejected] PASSED
tests/test_services_complaints.py::TestStateMachine::test_illegal_transitions_raise[resolved-open] PASSED
tests/test_services_complaints.py::TestStateMachine::test_illegal_transitions_raise[resolved-in_progress] PASSED
tests/test_services_complaints.py::TestStateMachine::test_illegal_transitions_raise[rejected-open] PASSED
tests/test_services_complaints.py::TestStateMachine::test_illegal_transitions_raise[rejected-in_progress] PASSED
tests/test_services_complaints.py::TestStateMachine::test_illegal_transitions_raise[open-resolved] PASSED
tests/test_services_complaints.py::TestStateMachine::test_illegal_transitions_raise[in_progress-open] PASSED
tests/test_services_complaints.py::TestStateMachine::test_missing_complaint_raises_not_found PASSED
tests/test_services_complaints.py::TestTriageOrchestration::test_submit_complaint_with_simulated_provider_round_trips PASSED
tests/test_services_complaints.py::TestTriageOrchestration::test_submit_complaint_with_rule_based_provider_round_trips PASSED
tests/test_services_complaints.py::TestMandatoryDeterminism::test_provider_that_always_raises_falls_back_deterministically PASSED
tests/test_services_complaints.py::TestStats::test_get_stats_matches_seed_distribution PASSED
============================== 15 passed in 0.88s ==============================
```

**New file alone, run 2 (order-dependency check):**
```
collected 15 items
... (identical 15 tests, identical order, all PASSED)
============================== 15 passed in 0.82s ==============================
```

**Combined with `test_repositories.py`, `test_schema.py`, `test_triage_providers.py`, `test_llm_triage.py`** (regression check now that this phase's tests share a real DB with Phase 3/4's):
```
collected 134 items
... (all 134 PASSED, including all 8 test_repositories.py cases,
    2 test_schema.py cases, 15 test_services_complaints.py cases,
    11 test_triage_providers.py cases + 36×2 seed-fixture parametrizations,
    26 test_llm_triage.py cases)
============================= 134 passed in 2.48s ==============================
```
Re-run after the ruff-driven comment-placement fix, same combined set:
```
134 passed in 2.19s
```

**ruff check .** (from `backend/`, after fix): `All checks passed!`

**mypy app** (from `backend/`): `Success: no issues found in 23 source files`

(One incidental finding, not a code defect: `pip install ".[dev]"` left a
root-owned `build/` directory under `backend/` — a setuptools side effect
of an editable/sdist-style install in the ephemeral container, already
covered by `.gitignore` and confirmed absent from `git status`. Removed
it anyway for hygiene: `rm -rf build`.)

### Manual Mandatory Determinism demonstration (outside pytest)

Per `docs/CONTRACTS.md` §2.5: *"Write this test if you write no other:
given a provider that always raises, POST /api/complaints still returns
201 and triaged_by == 'rules:fallback'."* (201/routes don't exist until
Phase 7; this demonstrates the service-layer half of that guarantee, same
precedent as the automated test above.) Ran directly against the real DB,
row cleaned up after:
```
triage_provider_raised_falling_back
triaged_by: rules:fallback
status: open
category: other
cleanup done
```

### No-secrets check

```
$ git status --short
 M docs/specs/phase-06-service-layer.md
?? backend/app/services/complaints.py
?? backend/app/services/exceptions.py
?? backend/tests/test_services_complaints.py
$ grep -rn "change-me\|AIzaSy\|api_key.*=.*['\"][A-Za-z0-9]" backend/app/services backend/tests/test_services_complaints.py docs/specs/phase-06-service-layer.md
no literal secrets found
```

### RUBRIC-CHECKLIST.md — audited, not edited

Checked whether this phase closes either of the two candidate Category C
lines. Neither does, and neither was touched:
- "Status state machine as an explicit transition table; invalid
  transitions 409" (3 marks) — the transition table and its enforcement
  (`IllegalTransitionError`) are done and tested, but the "409" half of
  this line is an HTTP-layer behaviour that doesn't exist until Phase 7.
  Left `[ ]`.
- "triage_latency_ms recorded and surfaced through /api/meta/providers"
  (2 marks) — recording is done (`submit_complaint()` measures and
  persists it), but "surfaced through /api/meta/providers" needs a route
  that doesn't exist yet. Left `[ ]`.

Updating `RUBRIC-CHECKLIST.md` was not a Deliverable in this phase's
approved Plan, so it was audited for accuracy but not edited — avoiding
undisclosed scope creep in either direction (silently checking a
half-true line, or silently rewriting the checklist unasked).

### Failure-mode audit (`docs/WORKFLOW.md`)

- **Silent decisions:** none beyond the one already flagged and approved
  in the Plan (OQ3's `NotFoundError`) and the comment-placement deviation
  noted above, which is a formatting change with no behavioural effect.
- **Unverified claims:** none — every Deliverable has pasted output above;
  the manual Determinism demonstration was run for real, not assumed from
  the pytest pass.
- **Undisclosed scope creep:** none. No file outside the Plan's three-file
  list was created or modified. `RUBRIC-CHECKLIST.md` was read for audit
  purposes only, per the paragraph above, and left untouched since editing
  it wasn't part of this phase's approved scope.

### Postgres teardown

`docker compose stop postgres` after verification — no long-running
containers left behind by this session.
