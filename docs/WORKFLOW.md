# Phase Workflow

The standing process for every phase from here on. This formalizes what Phases 2–4 already did in practice — see the "Process note" in each of `docs/specs/phase-02-project-setup.md` through `phase-04-repository-layer.md` for how those three differ from this.

## The six steps

1. **Select** — the next phase comes from `docs/IMPLEMENTATION-PLAN.md`, in dependency order. A phase isn't selected out of turn just because it sounds more interesting; its dependencies must already be done.
2. **Spec drafted and human-approved** — a spec is written against `docs/specs/TEMPLATE.md`'s shape and reviewed before anything else happens. No code, no scaffolding, while this step is open.
3. **Spec committed as its own commit, before any code exists** — `docs/specs/phase-NN-name.md` lands in a commit by itself. Implementation never starts from an uncommitted spec.
4. **Implementation against the committed spec file only** — never against the original chat instruction, never against memory of the discussion that produced the spec. If the spec turns out to be wrong once real code meets it, that's a stop-and-flag moment (see Ambiguity handling in the template), not a silent departure from the file.
5. **Verification with real, pasted command output** — every verification claim in the phase report is backed by an actual command's actual output, pasted, not summarized or asserted. "Tests pass" is not evidence; the pytest output is.
6. **Audit against three named failure modes, before the phase is marked done** — check explicitly for:
   - **Silent decisions** — did an ambiguity get resolved without being flagged?
   - **Unverified claims** — is anything in the report asserted without the command output to back it?
   - **Undisclosed scope creep** — did anything get built, renamed, or "improved" beyond the spec's Deliverables?

   Only after this audit does the phase get marked done and the living docs (`docs/RUBRIC-CHECKLIST.md`, `docs/OPEN-DECISIONS.md`, ADRs) get updated.

## The hard rule

**From Phase 5 onward: no phase gets implemented until its spec file exists in `docs/specs/` AND is committed.** No more backfilling specs after the fact — Phases 2–4 were backfilled because this process didn't exist yet when they were built; every phase after this one is spec-first for real.
