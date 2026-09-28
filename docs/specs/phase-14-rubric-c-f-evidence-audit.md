# Phase 14: Rubric checklist audit — Category C/F evidence pass
Status: not started (spec drafted, awaiting approval — Plan not yet started, per `docs/WORKFLOW.md` step 4)
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
_Not started — pending approval of this spec, per `docs/WORKFLOW.md` step 4._

## Verification required
_Not yet defined — depends on the Plan._

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md`, the current code, or is underspecified beyond what's captured above, stop and ask — do not silently resolve.

## As-Built
_Filled in after implementation._
