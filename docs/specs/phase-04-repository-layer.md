Status: backfilled retroactively — this spec was originally given as a
chat instruction and executed before this file existed. Content below is
reproduced verbatim from that instruction, not reconstructed from the
resulting code. See commit history and docs/RUBRIC-CHECKLIST.md for what
was actually delivered against it.

## Spec (as given)

Two small fixes, then Phase 4.

1. backend/app/scripts/seed.py: add a one-line comment above the
   triaged_by/ai_summary/triage_latency_ms fields stating these are
   synthetic fixture values for local testing/demo variety, not the
   result of an actual triage call — and a second comment noting the
   uuid5-derived id is a seed-only idempotency mechanism, never to be used
   in the real complaint-creation path (that must use the DB's
   gen_random_uuid() default with a fully random id).

2. No schema/migration changes — location's constraint stays as
   implemented (DB-level upper bound via VARCHAR(200), app-level minimum),
   confirmed correct per CONTRACTS.md's literal wording.

Then, Phase 4: Repository Layer. Read docs/CONTRACTS.md's API table again —
every repository function should map to something a route will need, don't
build speculative methods "just in case."

- backend/app/repositories/complaints.py: create(), get_by_id(), list()
  supporting filtering by status/category/priority (any combination, all
  optional) and pagination (matching whatever pagination shape CONTRACTS.md
  specifies for GET /api/complaints — cursor or offset, check and don't
  guess), update_status() for the PATCH endpoint, and a stats aggregation
  query serving GET /api/stats (counts by status, counts by category,
  average triage_latency_ms — check CONTRACTS.md for the exact shape
  expected). This file is the ONLY place raw SQL/ORM queries against the
  complaints table are allowed anywhere in the codebase from this point on.
- No status-transition validation here (e.g. rejecting an illegal status
  jump) — that's business logic for the Service layer next phase.
  update_status() just writes the value it's given; the state machine
  legality check happens above this layer. State this boundary explicitly
  in the file's module docstring so it's not ambiguous to future-you.
- backend/tests/test_repositories.py against the real Postgres (same
  pattern as test_schema.py): create then get_by_id round-trips correctly,
  list() filtering returns correct subsets for each filter and combinations,
  pagination doesn't duplicate or skip rows across pages, stats aggregation
  numbers are verified against a hand-counted expectation from the seeded
  data (not just "it returns something").
- Update docs/RUBRIC-CHECKLIST.md evidence column for lines now true.

Report back: what you built, the actual pytest output, and any CONTRACTS.md
ambiguity you hit (especially the pagination shape — flag clearly if it's
underspecified rather than picking one silently). Then stop — no services,
no routes, no state-machine logic yet.
