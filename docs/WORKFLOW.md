# Phase Workflow

The standing process for every phase from here on. This formalizes what Phases 2–4 already did in practice — see the "Process note" in each of `docs/specs/phase-02-project-setup.md` through `phase-04-repository-layer.md` for how those three differ from this.

## The steps, and four commits per phase

1. **Select** — the next phase comes from `docs/IMPLEMENTATION-PLAN.md`, in dependency order. A phase isn't selected out of turn just because it sounds more interesting; its dependencies must already be done.
2. **Spec drafted and human-approved** — a spec is written against `docs/specs/TEMPLATE.md`'s shape and reviewed before anything else happens. No code, no scaffolding, while this step is open.
3. **Commit 1 — Spec committed as its own commit, before any code exists** — `docs/specs/phase-NN-name.md` lands in a commit by itself. Implementation never starts from an uncommitted spec.
4. **Plan drafted and human-approved** — mandatory for every phase, no complexity exceptions: depth scales with the phase's actual complexity, existence doesn't. The template's `## Plan` section is filled in — files to be touched in order, key technical choices and why, open uncertainties — and approved before any code is written. A mechanically simple phase gets a short plan; a phase with real technical decisions gets a longer one. Neither gets none.
5. **Commit 2 — Plan committed after human approval, before any code exists** — the same spec file, now with `## Plan` filled in, committed on its own. Implementation never starts from an unapproved or uncommitted plan either.
6. **Implementation against the committed spec + plan only** — never against the original chat instruction, never against memory of the discussion that produced them. If either turns out to be wrong once real code meets it, that's a stop-and-flag moment (see Ambiguity handling in the template), not a silent departure from the file.
7. **Verification with real, pasted command output** — every verification claim in the phase report is backed by an actual command's actual output, pasted, not summarized or asserted. "Tests pass" is not evidence; the pytest output is.
8. **Commit 3 — implementation commit(s)** — the actual code, tests, and doc updates for the phase.
9. **Audit against three named failure modes, before the phase is marked done** — check explicitly for:
   - **Silent decisions** — did an ambiguity get resolved without being flagged?
   - **Unverified claims** — is anything in the report asserted without the command output to back it?
   - **Undisclosed scope creep** — did anything get built, renamed, or "improved" beyond the spec's Deliverables?
10. **Commit 4 — As-Built appended and committed** — the template's `## As-Built` section is filled in with real verification output and any deviation from the Plan or Spec, and committed. Only after this does the phase count as done and the living docs (`docs/RUBRIC-CHECKLIST.md`, `docs/OPEN-DECISIONS.md`, ADRs) get updated.

In short, four commits per phase, in order: **(1) Spec → (2) Plan → (3) Implementation → (4) As-Built.**

## The hard rule

**From Phase 5 onward: no phase gets implemented until its spec file exists in `docs/specs/` AND is committed, AND its `## Plan` section exists, is human-approved, AND is committed.** No more backfilling specs after the fact, and no skipping the Plan step for phases that look simple — depth scales with complexity, existence doesn't. Phases 2–4 were backfilled (no Plan step existed yet); every phase after this one is spec-then-plan-first for real.
