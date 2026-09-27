# Phase 13: Documentation close-out
Status: in progress, pending review
Depends on: everything (Phases 2–12) existing in at least draft form
Reads first: `docs/IMPLEMENTATION-PLAN.md` (Phase 13 entry), `docs/RUBRIC-CHECKLIST.md` (Category J + remaining §5.3 rows), `docs/CONTRACTS.md`, `docs/architecture/ARCHITECTURE.md`, `docs/WORKFLOW.md`, `Software Construction and Design -  Assignment 1.md` §4 Category J, §5.2, §5.3, §5.5, §5.7, §5.8

## Goal

Turn the project's real, already-verified state — spread across 12 phase specs' As-Built sections, `docs/adr/`, `docs/CONTRACTS.md`, and `docs/RUBRIC-CHECKLIST.md` — into the four portfolio documents Category J actually scores (README.md, `docs/RUNBOOK.md`, `docs/ENGINEERING-NOTES.md`) plus the honest-attribution document §5.5 requires (`docs/AI-USAGE.md`), a demo-video shot list, and a final truthful pass over `docs/RUBRIC-CHECKLIST.md`. This phase writes no application code and makes no architectural decisions — it cites and packages decisions already made, and where a citable answer doesn't exist yet, it says so as an Open Question rather than inventing one.

## Deliverables

- `README.md` — replaces the 5-line stub. Problem statement, CI/CD status badges (real GitHub Actions badge URLs for `ci.yml`/`cd.yml`/`release.yml`), a Mermaid architecture diagram (derived from `docs/architecture/ARCHITECTURE.md`, not invented fresh), a literally-tested one-command quickstart (`docker compose up` from a real clean-clone test — see Open Question 1), the 9-endpoint API table (from `docs/CONTRACTS.md` §2.2, not retyped by hand — copy it), and screenshots (frontend views — see Open Question 2 for what's actually achievable).
- `docs/RUNBOOK.md` — new file. How to deploy (compose + k8s paths), how to roll back (image-tag/SHA revert, per `docs/adr/0003-deploy-by-sha.md`), how to read logs (structured JSON to stdout — but see Ambiguity-handling: Category C's structured-logging row is currently `[ ]` unimplemented), and what to do when triage starts failing (fallback path, per `docs/adr/0001-provider-interface.md` and the LLM provider's retry/fallback behaviour).
- `docs/ENGINEERING-NOTES.md` — new file, all eight §5.2 questions answered with real file-and-line citations from this repository, not generic answers.
- `docs/AI-USAGE.md` — new file, per §5.5: naming the tools used, which parts they wrote or shaped, and what was changed afterward and why. Required by course policy regardless of Category J's marks table (§5.5 is separate from J's four scored line items — see Ambiguity-handling).
- Demo-video shot list — a script/outline only (see Open Question 3), not the video itself.
- Final pass over `docs/RUBRIC-CHECKLIST.md` — Category J rows filled in with real citations once the above exist; a second pass over any other row that's gone stale since it was last touched.

## Non-goals

- No application code, no Dockerfile/manifest/workflow changes. Pure documentation.
- No new ADRs decided in this phase preemptively — Open Question 4 asks whether any are actually missing; none get written speculatively.
- No attempt to actually record or produce the demo video — that requires a human with a microphone (§5.4's viva logic applies here too: a script Claude "performed" would be exactly the kind of AI-presented-as-own-work the course policy at §5.5 flags).
- No final §5.8 submission packaging (GHCR links, `git shortlog -sn` paste, HPA capture bundling) — those are submission-time actions performed once, immediately before submitting, not documentation artifacts this phase produces.
- Category A (collaboration) rows are not touched here beyond what's already accurately `[ ]`/at-risk in `docs/RUBRIC-CHECKLIST.md` — this phase doesn't change that reality.
- Bonus scope (`docs/OPEN-DECISIONS.md` #10) stays out of scope, same as Phase 12.

## Open Questions

1. **README quickstart verification method.** I have no way to provision a genuinely fresh machine (no OS install, no unconfigured Docker daemon). The real test I can run: `git clone` the actual GitHub remote (`https://github.com/Zain-Shykh/Civic-Pulse.git`) into a brand-new directory outside this working tree, then follow the README's own steps verbatim (`cp .env.example .env`, fill required vars, `docker compose up`) with no reuse of this working tree's `.env` or any manual pre-step not written in the README. Caveat, stated up front rather than glossed over later: this machine's Docker daemon already has the base images (`python:3.12-slim`, `node:22-alpine`, `nginx:1.31-alpine`, `postgres:16-alpine`, `redis:7-alpine`) cached from earlier phases, so this does not prove a true first-ever pull on a machine with an empty image cache — only that the compose file, `.env.example`, and README steps are internally consistent and complete. That distinction goes in the As-Built verbatim, not summarized as "clean clone verified."
2. **Frontend screenshots.** Same limitation as Phase 12 (no browser/screenshot tool available to me) — flagged here up front instead of discovered mid-implementation. `docs/evidence/` currently only has the two Phase 12 CI screenshots. Options: (a) the user captures the frontend screenshots (Submit/Dashboard/Stats) and drops them in `docs/evidence/`, same pattern as PR #15's CI screenshots; (b) README ships without frontend screenshots and that gap is disclosed in the As-Built and `docs/RUBRIC-CHECKLIST.md`'s J-row rather than silently left unchecked with no explanation. Needs a decision before README's screenshot section is finalized — not decided here.
3. **Demo video.** §J asks for "≤5 min, both partners speaking" — a real recording. My deliverable is a shot-list/script (scenes, what's shown, rough timing, which command runs on-screen) that a human follows to record it. I will not claim to have "produced" the video, and `docs/RUBRIC-CHECKLIST.md`'s video row stays `[ ]` until an actual recording exists and is linked (also gated by the same partner-availability risk already tracked in Category A).
4. **Are any more ADRs actually missing?** The assignment names exactly four required ADRs (provider interface, frontend runtime config, deploy-by-SHA, PII/data governance) — all four exist (`0001`–`0004`), plus one extra (`0005`, the `/ready`-layering exception, not required by the assignment but written anyway). Several other real decisions got made along the way and are currently documented only inside phase-spec As-Builts, not as standalone ADRs: the Traefik `service.spec.type` Helm-value-path fix (Phase 12), the VPA-CRD-only install choice on `kind` (Phase 12) vs. the real VPA-controller install on k3d (Phase 11b), and the nginx `1.27→1.31-alpine` base-image bump (Phase 12). None of these were flagged as needing an ADR when they happened. Question for the user: leave them as-is (documented in their originating phase's As-Built, which is where `docs/RUBRIC-CHECKLIST.md` already cites them), or promote any of them to standalone ADRs now? Not decided here.
5. **The repository layout in the assignment text (§5.7) names two things neither `docs/IMPLEMENTATION-PLAN.md` nor `docs/RUBRIC-CHECKLIST.md` currently mention anywhere: `docs/TRIAGE.md` and `scripts/check_submission.py`.** Verified directly — neither file exists in this repo, and neither is referenced by any rubric row or marks line. `check_submission.py` is described (§5.8) as a pre-submission lint the assignment expects to exist and run clean, with no spec for what it should check beyond "catches the mechanical failures behind most of §5.3." `TRIAGE.md` is never described anywhere outside the layout tree. Real gap, not invented: does this phase write these two, and if so, what does `check_submission.py` actually check? Not decided here — needs an answer before Deliverables above are treated as complete.

## Plan

_To be filled in and approved before any of the Deliverables are written, per `docs/WORKFLOW.md` step 4. Depends on the answers to Open Questions 1–5 above — in particular, Open Question 5's answer changes the Deliverables list itself, and Open Question 2's answer changes what README's screenshot section can actually contain._

## Verification required

_To be finalized alongside the Plan. Provisionally, at minimum:_
- The literal clone/quickstart command sequence from Open Question 1, real terminal output pasted.
- `docs/ENGINEERING-NOTES.md`'s eight answers cross-checked one by one against the file:line each one cites (the citation must actually say what the note claims).
- A diff-based check that README's API table matches `docs/CONTRACTS.md`'s current table verbatim (not hand-retyped and drifted).
- `docs/RUBRIC-CHECKLIST.md`'s J rows and any other touched row cross-checked against the real file each one cites.

## Ambiguity handling

- `docs/AI-USAGE.md` is required by §5.5 but is not one of Category J's four scored line items (README, ADRs, RUNBOOK, video, ENGINEERING-NOTES are the five J rows actually listed with marks in both the assignment text and `docs/RUBRIC-CHECKLIST.md`; §5.5's AI-USAGE requirement sits outside that table, tied to plagiarism policy instead). Building it anyway, folded into this phase for practical reasons (it belongs with the other portfolio docs), but not silently counted toward J's 15 marks in `docs/RUBRIC-CHECKLIST.md` — it gets its own note, not a merged row.
- `docs/RUNBOOK.md`'s "how to read logs" section will describe the *intended* structured-JSON-with-request_id logging design per `docs/CONTRACTS.md`/ADRs, but Category C's row for that ("Structured JSON logging to stdout with a propagated request_id") is currently `[ ]` — unimplemented, confirmed by checking `docs/RUBRIC-CHECKLIST.md` directly rather than assumed. The RUNBOOK will not claim this exists; it will describe what's actually there today (`docker compose logs`/`kubectl logs`, whatever format is real right now) and flag the gap rather than writing the runbook against an aspirational feature.
- Open Questions 1–5 above are exactly the "stop and ask" cases `docs/WORKFLOW.md` and `CLAUDE.md` require — none of them get a silent default. This spec stops here, before any Plan work, per the pasted instruction that started this phase.

## As-Built

_Filled in after implementation._
