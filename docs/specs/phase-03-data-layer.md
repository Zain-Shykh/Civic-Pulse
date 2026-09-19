Status: backfilled retroactively — this spec was originally given as a
chat instruction and executed before this file existed. Content below is
reproduced verbatim from that instruction, not reconstructed from the
resulting code. See commit history and docs/RUBRIC-CHECKLIST.md for what
was actually delivered against it.

## Spec (as given)

Phase 3: Data Layer. Read docs/CONTRACTS.md and docs/architecture/SCHEMA.md
first — they are the only source of truth for schema shape. Do not add,
rename, or "improve" any field, enum value, or index beyond what's written
there. If you think something in CONTRACTS.md is wrong or incomplete now
that you're implementing it for real, STOP and flag it to me rather than
silently fixing it.

1. Alembic migration (backend/alembic/versions/) creating the schema
   exactly as specified in CONTRACTS.md/SCHEMA.md — table, enum types,
   both required indexes, defaults, constraints. Must have a working
   downgrade(), not just upgrade(). No other tables, no speculative columns
   "for later."

2. Idempotent seed script (backend/app/scripts/seed.py or equivalent, NOT
   baked into the Alembic migration — migrations stay schema-only) that
   inserts at least 30 realistic complaints in Urdu-influenced English
   phrasing, spread across a realistic mix of every status, priority, and
   category value the schema defines — later phases (stats aggregation,
   dashboard filtering, pagination) need real variety to test against, not
   30 copies of the same row. Running the script twice must not create
   duplicates or error — check-before-insert or an upsert key, your choice,
   but state which in the script's docstring.

3. Verify against a REAL Postgres, not just "it imported cleanly":
   - docker compose up -d postgres (reuse Phase 2's skeleton)
   - alembic upgrade head against it — must succeed
   - alembic downgrade base then upgrade head again — must be clean, proves
     the migration is genuinely reversible, not just forward-only
   - Run the seed script, run it a second time, confirm no duplicates
   - Query information_schema (or \d in psql) and paste the actual output
     showing the table structure matches CONTRACTS.md field-for-field —
     don't just assert it matches, show the real output
   - Confirm both required indexes exist via pg_indexes, paste that output too

4. A pytest test (backend/tests/) that spins up against the real DB (reuse
   whatever fixture/connection pattern makes sense — you decide, but it
   must hit real Postgres, not a mock) and asserts: the enum constraints
   actually reject an invalid value, and the two indexes exist. This is the
   first real test in the suite — set the pattern future test phases will
   follow.

5. Update docs/RUBRIC-CHECKLIST.md's evidence column only for lines now
   genuinely true (schema matches contract, migration reversible, etc.)

No repository layer yet — no query functions beyond what's needed for the
verification test above. That's Phase 4. Report back: the actual command
output from step 3 (all of it, not summarized), what the seed data looks
like (a few sample rows), and any ambiguity or CONTRACTS.md gap you hit.
Then stop.
if any env variable or setup is required to complete the task then ask me for it before starting.
