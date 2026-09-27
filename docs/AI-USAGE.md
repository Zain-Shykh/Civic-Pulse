# AI usage disclosure (assignment §5.5)

Per §5.5: honest attribution, not avoidance. This names the tool, how it was actually used across this repository, and what got changed, rejected, or corrected along the way — not a generic "AI helped with everything" statement.

## The tool

Claude Code (Anthropic), running Claude models — most recently Claude Sonnet 5 (`claude-sonnet-5`) for this phase's work; earlier phases in this repository's history used whichever Claude Code model was current at the time. Referred to below as "the assistant."

## The actual working pattern

Every phase in this repository followed the four-commit discipline in `docs/WORKFLOW.md`: the assistant drafts a spec, the human reviews and either approves it or sends it back with named objections, the assistant drafts a Plan against the approved spec, the human approves the Plan, the assistant implements against the committed spec+plan (never against chat memory of the discussion that produced them), and the assistant writes the As-Built with real command output. Nothing in this repository was written by the assistant working unsupervised end-to-end — every phase has a human-approval gate before implementation starts, visible directly in the git history as separate spec/plan/implementation/as-built commits per phase (`docs/specs/phase-*.md`).

**What the assistant wrote or shaped:** the large majority of the code, Dockerfiles, Kubernetes manifests, GitHub Actions workflows, and documentation in this repository, including this file. Draft specs, draft Plans, and every As-Built's evidence-gathering (running commands, pasting real output) were produced by the assistant.

**What the human decided, not the assistant** — real examples, not a generic claim, each cross-referenced to where the decision is actually recorded:

- Every entry in `docs/OPEN-DECISIONS.md` marked "Reasoning (human's own)" — e.g. FastAPI over Flask (`docs/OPEN-DECISIONS.md:45`), Kustomize over Helm (`:51`), k3d over kind (`:57`), fixed-window over token-bucket rate limiting (`:75`), k6 over `hey` (`:81`) — the assistant surfaced the tradeoff, the human picked.
- The PII/redaction stance (`docs/adr/0004-pii-and-data-governance.md`) — the assistant identified the exposure and the mechanically available options; the human chose the hybrid regex approach over full NER-based scrubbing or accept-and-document-only.
- This phase's five Open Questions (`docs/specs/phase-13-documentation-closeout.md`) — the quickstart-verification method, the frontend-screenshot gap, the demo-video scope, whether more ADRs were needed, and whether to write `docs/TRIAGE.md`/`scripts/check_submission.py` — were all raised by the assistant and resolved by explicit human instruction before any Plan work started, not silently decided either way.
- Phase 12's Trivy-driven `nginx:1.27-alpine` → `nginx:1.31-alpine` base-image bump (`docs/RUBRIC-CHECKLIST.md`'s Category G table) — a real, disclosed deviation from the assignment's literal pinned-version text, made only after the human was told exactly why (40 real fixable CVEs on the literal tag) and approved the deviation rather than it being silently substituted.

**What got corrected, and why** — the clearest real example is Phase 12's Traefik `helm --wait` timeout (`docs/specs/phase-12-ci-cd.md`, PRs #10–#12, quoted in full in `docs/ENGINEERING-NOTES.md` Q8): the assistant's first fix attempt (`--set service.type=ClusterIP`) was wrong — Helm silently ignored that value path rather than erroring — and was only caught by adding a real diagnostic step and testing the correct path (`service.spec.type`) locally with `helm template` before pushing a second fix. This is left in the repository's history as three separate PRs, not squashed into a single "fixed Traefik" commit, because the wrong attempt and why it was wrong is itself real information (this is exactly what `docs/ENGINEERING-NOTES.md` Q8 asks for).

## What this means at the viva (§5.4)

Per §5.4 and this file's own opening line: the viva does not care who typed a line, only whether it can be defended. Every non-trivial decision in this repository has a citable reason attached to it — an ADR, an `OPEN-DECISIONS.md` entry, a spec's Open Questions section, or an As-Built's disclosed deviation — specifically so that "why is this here" always has a real answer to give, not "the AI wrote it that way."
