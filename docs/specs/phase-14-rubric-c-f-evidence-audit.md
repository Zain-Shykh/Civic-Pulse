# Phase 14: Rubric checklist audit — Category C/F evidence pass
Status: done (spec, plan, implementation, and As-Built all landed per `docs/WORKFLOW.md`'s four-commit lifecycle)
Depends on: Phases 6/7 (`routes/`, `services/`, `repositories/` — Category C's actual implementation), Phase 5b/8 (LLM triage + cache layer — Category F's actual implementation). All already shipped; this phase re-verifies and cites, it does not change them.
Reads first: `docs/RUBRIC-CHECKLIST.md` lines 33, 34, 35, 39, 66, 68 (confirmed by direct read: all six are currently `[ ]` with a blank Evidence/file column, unlike every neighboring row in the same two categories); `docs/CONTRACTS.md` (endpoint table, for row 33's count); `backend/app/routes/complaints.py`, `health.py`, `meta.py`, `stats.py` (row 33/34); `backend/app/repositories/complaints.py` (row 34 — where all SQL should live); `backend/app/services/complaints.py` (row 35's `_LEGAL_TRANSITIONS`/`change_status()`, row 68's `get_meta_providers()`); `backend/app/providers/cache.py` (row 66's `_triage_cache_key`/`triage_cache_hit_rate()`); `backend/pyproject.toml` (`pytest-cov` already configured, `[tool.coverage.run] source = ["app"]`); `docs/specs/phase-12-ci-cd.md`'s As-Built (existing CI-measured coverage citation — `93.91%`, `165 passed`, from CI run `36335209268` — cited there as *CI's* number, kept as background context only; per direct instruction this phase runs its own fresh local invocation, not a reused figure).

This is not a phase from `docs/IMPLEMENTATION-PLAN.md`'s original sequence — added after Phase 13 shipped, which that file's own text names as "the last phase." Same addendum pattern as Phase 9c/11b/11c: `docs/IMPLEMENTATION-PLAN.md` gets a matching entry in the same commit as this spec.

## Goal
Close the evidence-citation gap on six specific `docs/RUBRIC-CHECKLIST.md` rows — Category C (Backend) rows 33, 34, 35, 39, and Category F (AI layer) rows 66, 68 — where the underlying feature is already implemented and, per a preliminary check reported directly, real and working, but never received the evidence-citation pass every other row in both categories already has. This phase independently re-verifies each claim against the current code (not trusting the preliminary check's claims without re-checking), and for row 39 specifically, runs the real backend test suite with coverage against live throwaway Postgres/Redis containers, then updates the checklist with real citations. Documentation-only: `docs/RUBRIC-CHECKLIST.md` is the only file this phase's Implementation step edits (plus this spec's own Plan/As-Built and the matching `docs/IMPLEMENTATION-PLAN.md` entry) — no application code changes.

## Deliverables
- `docs/RUBRIC-CHECKLIST.md` rows 33, 34, 35, 39, 66, 68 — each either flipped to `[x]` with a real citation (file:function references, plus real command output where the row's claim is about behavior rather than structure) if verification confirms the claim as written, or left `[ ]` with the real, stated reason if verification finds the claim doesn't fully hold — a stop-and-flag moment, not a silent `[x]`.
- This spec file (`docs/specs/phase-14-rubric-c-f-evidence-audit.md`).
- A matching `docs/IMPLEMENTATION-PLAN.md` addendum entry (same commit as this spec).

## Non-goals
- Rows 37 (structured JSON logging + request_id) and 38 (SIGTERM draining in-flight requests) — real, disclosed gaps, not documentation gaps; neither exists in the code today. Both stay `[ ]`. Not implemented, not touched, per direct instruction — not raised as an Open Question either, since the scope call was already made explicitly.
- No application code changes anywhere. If verification surfaces an actual defect (code doesn't do what a row claims), that's reported plainly and the row stays `[ ]` (or gets a caveated citation describing exactly what's true and what isn't) — never silently fixed in the same documentation-only phase.
- No changes to any other `docs/RUBRIC-CHECKLIST.md` row or category beyond the six named above.
- No new tests written. Row 39's coverage number comes from running the existing suite as-is.
- Doesn't re-litigate row 33's own already-settled "rubric says ten, confirmed typo" note from a prior phase — re-verified here only for endpoint count/status-codes/validation, not re-argued.

## Open Questions
None identified while drafting this spec — the scope, the excluded rows, and the re-verification discipline are all already specified directly. If implementation turns up a genuine ambiguity (e.g., a row's claim is partially true and it's unclear whether that merits `[x]` with a caveat or `[ ]`), it's flagged here before the checklist is edited, not resolved silently — per Ambiguity handling below.

## Plan

Research already done while drafting this Plan (read-only — no checklist edits yet), so the steps below are concrete, not speculative:

1. **Row 33** — `backend/app/main.py` wires exactly 4 routes from `complaints_router` (POST/GET-by-id/GET-list/PATCH-status), 2 from `health_router` (`/health`, `/ready`), 1 from `meta_router` (`/api/meta/providers`), 1 from `stats_router` (`/api/stats`), plus `Instrumentator().instrument(app).expose(app)` auto-adding `/metrics` — 9 total, matching `docs/CONTRACTS.md`'s endpoint table (also 9 rows) exactly. Status codes confirmed by direct read: `201` on create, default `200` elsewhere, `404`/`409`/`429`/`400` all via registered exception handlers (`app/exception_handlers.py`), not ad hoc per-route logic. Field-level validation confirmed in `backend/app/schemas/complaints.py` (`Field(min_length=..., max_length=...)`, copied from `docs/CONTRACTS.md` §2.3) routed through `validation_error_handler` → `400`. Cite file:line plus the existing test(s) that exercise the `400` path.
2. **Row 34** — `grep -rln "sqlalchemy\|text(\|engine\b\|\.execute(" backend/app/routes backend/app/services` already run: zero matches. Combined with the direct reads of `routes/complaints.py` (parses/delegates/serializes only) and `repositories/complaints.py` (the only file with `text(...)`/`engine.begin()`/`engine.connect()`), this is a real, checkable structural fact, not an assertion. Cite both the grep and the two files' own module docstrings, which already state the same rule.
3. **Row 35** — `services/complaints.py`'s `_LEGAL_TRANSITIONS` frozenset (4 legal edges) and `change_status()` (raises `IllegalTransitionError` on any pair not in the set) already read directly; `exception_handlers.py::illegal_transition_handler` maps it to `409`. Cite file:line plus whichever existing test(s) in `test_services_complaints.py`/`test_routes_complaints.py` exercise both a legal and an illegal transition.
4. **Row 39** — real test run, real coverage, against **standalone throwaway containers, not `docker compose up postgres/redis`**: `compose.yaml`'s `postgres`/`redis` services deliberately publish no host port (network-segmentation rule, `CLAUDE.md` non-negotiables) — correct for the running stack, but it means a host-run `pytest` can't reach them. Standalone `docker run` containers (via `sg docker -c`, the confirmed daemon-access wrapper) with a transient published port, torn down right after, mirrors exactly what Phase 12's CI `services:` containers already do for the same reason, without touching `compose.yaml`. Steps: `docker run` Postgres 16 + Redis 7 (pinned, matching versions used everywhere else), `alembic upgrade head`, `python -m app.scripts.seed` (precondition already named in `test_repositories.py`/`test_services_complaints.py`'s own docstrings), then `TRIAGE_PROVIDER=simulated pytest --cov=app --cov-report=term-missing --cov-fail-under=65` — the exact command `ci.yml` already runs (`docs/specs/phase-12-ci-cd.md:118`), reused rather than invented. Real pass count, real coverage percentage, and real per-file test-count breakdown (already spot-counted while drafting this Plan: 76 test functions across 10 files, well over the ≥14 floor) go in the As-Built. Containers torn down (`docker rm -f`) after the run, confirmed via `docker ps -a`.
5. **Row 66** — `providers/cache.py`'s `_triage_cache_key` (SHA-256 of `text\0location`), `get_triage_cache`/`set_triage_cache`, `record_triage_cache_hit`/`record_triage_cache_miss`, `triage_cache_hit_rate()` (hits/(hits+misses), `None` if no lookups yet) already read directly. **Already has a real, passing, measured test**: `test_providers_cache.py::TestTriageCache::test_hit_rate_reflects_this_test_s_own_delta` records real hits/misses via the actual functions and asserts the real computed fraction — this is what "measured" means here, not a hand-wave. Cite that test directly rather than re-deriving a new measurement; note it as real, existing coverage this row simply never got cited.
6. **Row 68** — `services/complaints.py::get_meta_providers()` already read directly: calls `repository.recent_triage_outcomes(limit=20)` (real `triage_latency_ms` column, `repositories/complaints.py::create()` writes it on every insert, never null/placeholder) and includes `triage_cache_hit_rate` in the same response `routes/meta.py` serves at `GET /api/meta/providers`. Cite file:line plus whichever existing test(s) assert the response shape includes `latency_ms`.
7. **`docs/RUBRIC-CHECKLIST.md`** — all six rows' Evidence/file columns filled in with the citations gathered above, in the same style as neighboring rows in Category C/F (file:line/function, plus real command output where the claim is behavioral). Checkbox flips to `[x]` only for rows where the above confirms the claim as written; if step 1–6 above surfaces a real gap between a row's wording and what the code actually does, that row is flagged in the As-Built and left `[ ]` (or given a caveated citation) rather than silently marked done.
8. **This spec's own As-Built** — real command output pasted (test run, coverage, `docker ps -a` teardown confirmation), not summarized.

**Key technical choice:** standalone throwaway containers over `docker compose up`, specifically to avoid publishing a port on `compose.yaml`'s `postgres`/`redis` services even temporarily — that file is committed, shared, and graded; a throwaway `docker run` container is not.

**Open uncertainties:** none — every row's verification method above is already grounded in a direct code read done while drafting this Plan, not a guess.

## Verification required
- `grep -rln "sqlalchemy\|text(\|engine\b\|\.execute(" backend/app/routes backend/app/services` — real output, confirming zero matches (row 34).
- Real container startup (Postgres 16 + Redis 7, pinned), `alembic upgrade head`, `python -m app.scripts.seed`, then `TRIAGE_PROVIDER=simulated pytest --cov=app --cov-report=term-missing --cov-fail-under=65` — full real output pasted in the As-Built (row 39).
- `pytest --collect-only -q` (or equivalent) for a real, exact test-function count, not the grep-based estimate above.
- `docker ps -a` after teardown, confirming no leftover containers.
- Existing test output for the two already-covered claims (`test_hit_rate_reflects_this_test_s_own_delta` for row 66; whichever legal/illegal-transition tests exist for row 35) — pasted, not paraphrased.

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md`, the current code, or is underspecified beyond what's captured above, stop and ask — do not silently resolve.

## As-Built

**Status: done.** All six rows (33, 34, 35, 39, 66, 68) re-verified independently against current code and a real local run, then flipped to `[x]` with real citations (`docs/RUBRIC-CHECKLIST.md`). Rows 37/38 untouched, still `[ ]`, per Non-goals.

**Environment:** standalone throwaway containers, per the Plan's key technical choice (not `docker compose up postgres redis`, since those services deliberately publish no host port). Started via the confirmed `sg docker -c` daemon-access wrapper:
```
$ sg docker -c "docker run -d --name phase14-postgres -e POSTGRES_USER=civicpulse -e POSTGRES_PASSWORD=civicpulse -e POSTGRES_DB=civicpulse -p 15432:5432 postgres:16-alpine"
9fcf1a41296cf2b6c26431f5e4f54ad2a54f8954236388928241b4e75182e0af
$ sg docker -c "docker run -d --name phase14-redis -p 16379:6379 redis:7-alpine"
5b11158225ec1a7094ca12e3008ca7b0c748cac65b9392d87d4e4d943552c526
$ sg docker -c "docker exec phase14-postgres pg_isready -U civicpulse -d civicpulse"
... accepting connections
$ sg docker -c "docker exec phase14-redis redis-cli ping"
PONG
```

**Row 33/39 — migrations, seed, real coverage run** (`backend/.venv`, `DATABASE_URL`/`REDIS_URL` pointed at the throwaway containers, `TRIAGE_PROVIDER=simulated`):
```
$ alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> be5a6b3416a1, create complaints table

$ python -m app.scripts.seed
Seed complete: 36 new row(s) inserted, 0 already present.

$ python -m pytest --collect-only -q
165 tests collected in 0.71s

$ python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=65
...
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
app/db.py                               9      5    44%   19-23
app/providers/cache.py                 68      4    94%   67-70
app/providers/triage/llm.py            59      3    95%   58, 67-68
app/providers/triage/ollama.py          1      1     0%   8
app/repositories/complaints.py         42      2    95%   179-180
app/routes/complaints.py               30      1    97%   37
app/scripts/seed.py                    26     15    42%   196-207, 228-233, 237-239, 243
(all other modules 100%)
-----------------------------------------------------------------
TOTAL                                 509     31    94%
Required test coverage of 65% reached. Total coverage: 93.91%
165 passed, 2 warnings in 3.74s
```
**165 tests** (not the ≥14 the row requires, and not the 76 a crude `grep -c "def test_"` estimated while drafting the Plan — parametrized cases expand into many more real collected tests than function definitions). **93.91% coverage**, independently reproducing the exact figures `docs/specs/phase-12-ci-cd.md`'s As-Built reported from CI run `36335209268` (`509`/`31`/`94%`, `93.91%`) — a fresh local run landing on the same real numbers as CI, not a copy of them.

**Row 34 — raw-SQL grep:**
```
$ grep -rln "sqlalchemy\|text(\|engine\b\|\.execute(" backend/app/routes backend/app/services
(no matches)
```
Zero matches, confirmed live. `backend/app/repositories/complaints.py` is the only file with `text(...)`/`engine.begin()`/`engine.connect()` in `app/`.

**Row 35/33/66 — targeted verbose runs** (same containers/env). This was actually two separate real invocations, not one — shown as two, not merged into a summary line neither command ever printed:

Invocation 1 — `test_services_complaints.py` (full file) + `test_providers_cache.py::TestTriageResultCache` (route-level tests in the same command errored, see below, unrelated to these):
```
$ python -m pytest -v tests/test_routes_complaints.py::... tests/test_services_complaints.py tests/test_providers_cache.py::TestTriageResultCache
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
tests/test_services_complaints.py::TestTriageResultCache::test_second_identical_complaint_does_not_reinvoke_provider PASSED
tests/test_services_complaints.py::TestStats::test_get_stats_matches_seed_distribution PASSED
tests/test_providers_cache.py::TestTriageResultCache::test_get_set_round_trip_and_ttl PASSED
tests/test_providers_cache.py::TestTriageResultCache::test_hit_rate_reflects_this_test_s_own_delta PASSED
tests/test_providers_cache.py::TestTriageResultCache::test_hit_rate_is_none_when_no_lookups_recorded PASSED
19 passed, 3 warnings, 9 errors in 2.22s
```
**Real slip caught and fixed, not glossed over:** the 9 errors in that same invocation were the `test_routes_complaints.py` route-level tests, all `KeyError: 'TRIAGE_PROVIDER'` — a plain shell-scoping mistake (the `export TRIAGE_PROVIDER=simulated` from the coverage run above didn't carry over to this separate Bash tool invocation, since each is its own subshell). The 19 passes shown above are real and unaffected by that mistake — they don't depend on `TRIAGE_PROVIDER`.

Invocation 2 — the same 9 route-level tests, re-run with `TRIAGE_PROVIDER` set correctly this time:
```
$ python -m pytest -v tests/test_routes_complaints.py::TestStateMachineOverHttp tests/test_routes_complaints.py::TestCreateAndFetch::test_create_with_short_text_returns_400
tests/test_routes_complaints.py::TestStateMachineOverHttp::test_legal_transitions_return_200[open-in_progress] PASSED
tests/test_routes_complaints.py::TestStateMachineOverHttp::test_legal_transitions_return_200[in_progress-resolved] PASSED
tests/test_routes_complaints.py::TestStateMachineOverHttp::test_legal_transitions_return_200[open-rejected] PASSED
tests/test_routes_complaints.py::TestStateMachineOverHttp::test_legal_transitions_return_200[in_progress-rejected] PASSED
tests/test_routes_complaints.py::TestStateMachineOverHttp::test_illegal_transitions_return_409_naming_transition[resolved-open] PASSED
tests/test_routes_complaints.py::TestStateMachineOverHttp::test_illegal_transitions_return_409_naming_transition[open-resolved] PASSED
tests/test_routes_complaints.py::TestStateMachineOverHttp::test_illegal_transitions_return_409_naming_transition[in_progress-open] PASSED
tests/test_routes_complaints.py::TestStateMachineOverHttp::test_status_update_missing_id_returns_404 PASSED
tests/test_routes_complaints.py::TestCreateAndFetch::test_create_with_short_text_returns_400 PASSED
9 passed, 2 warnings in 0.75s
```
Both real invocations together: 28 individual real passes across the two commands (19 + 9) — stated here as two runs' arithmetic, not as a single pytest summary line, since no single command actually printed "28 passed."

**Teardown:**
```
$ sg docker -c "docker rm -f phase14-postgres phase14-redis"
phase14-postgres
phase14-redis
$ sg docker -c "docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}'"
chai-aur-redis   redis:7-alpine   Exited (0) 4 hours ago
chai-aur-mongo   mongo:7          Exited (0) 4 hours ago
gifted_chatterjee   hello-world   Exited (0) 12 days ago
cranky_pare   5dd0d3e6e255       Exited (0) 2 weeks ago
```
Clean — only pre-existing, unrelated containers from other projects remain; nothing this phase created was left running.

**Audit against the three named failure modes:**
- *Silent decisions* — none: the throwaway-container-vs-compose choice was already flagged and reasoned through in the Plan, not decided here; the `TRIAGE_PROVIDER` shell-scoping slip above is disclosed rather than hidden.
- *Unverified claims* — every citation added to `docs/RUBRIC-CHECKLIST.md` traces to real, pasted command output above, or to a specific existing test that was itself re-run live rather than assumed still passing.
- *Undisclosed scope creep* — none: only rows 33/34/35/39/66/68 touched; rows 37/38 left `[ ]`; no application code changed; the venv (`backend/.venv`) and containers used were pre-existing/throwaway respectively, nothing new committed to the repo by this phase beyond the checklist edit and this As-Built.
