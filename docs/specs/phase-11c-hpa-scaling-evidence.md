# Phase 11c: HPA/VPA scaling evidence capture
Status: not started (spec drafted, awaiting approval — Plan not yet started, per `docs/WORKFLOW.md` step 4)
Depends on: Phase 11b (`docs/specs/phase-11b-failfast-and-vpa-verification.md`) — reuses its already-verified real load-test data; no new k3d cluster run is currently planned, pending Open Question 1's decision.
Reads first: `docs/specs/phase-11b-failfast-and-vpa-verification.md`'s As-Built (real HPA/VPA numbers, lines 190–306); the assignment's §5.7 "Repository layout" (`docs/evidence/` comment: "screenshots: protection, conflict, blocked merge, hpa -w, scaling chart") and §5.8 "Submission" item 6 ("kubectl get hpa -w capture and your replicas-vs-load chart") verbatim; `docs/RUBRIC-CHECKLIST.md` line 90 (already `[x]`, citing Phase 11b's As-Built prose directly — this phase produces the durable file that row's evidence column currently lacks, not a re-derived analysis); `docs/DEMO-SCRIPT.md` Scene 5 (already cites the same Phase 11b data for the demo video).

This is not a phase from `docs/IMPLEMENTATION-PLAN.md`'s original sequence — added after Phase 11b shipped, same pattern as Phase 11b was to Phase 11 (and 9c to 9). `docs/IMPLEMENTATION-PLAN.md` gets a matching entry in the same commit as this spec.

## Goal
Produce the two durable evidence files the assignment names and that currently don't exist anywhere in the repo: a `kubectl get hpa -w` capture and a replicas-vs-load chart, both under `docs/evidence/`. Phase 11b already produced the real underlying data — a live k3d cluster, a real k6-driven load test, a genuine `2 → 3` HPA scale-out sustained at 79–89% utilization, and the tuned 300s scale-down back to the `minReplicas: 2` floor — but that cluster was torn down afterward, and the evidence currently lives only as prose/pasted output inside `docs/specs/phase-11b-failfast-and-vpa-verification.md`'s As-Built, not as the standalone files §5.7/§5.8 name. This phase turns already-real, already-verified data into committed artifact files. It does not re-derive the HPA/VPA analysis, and — per Open Question 1 below — does not currently plan to re-run the load test either.

## Deliverables
Tentative, finalized once the Open Questions below are resolved and the Plan is drafted:
- `docs/evidence/hpa-scaling.txt` (or `.png`, pending Open Question 2) — the real `kubectl get hpa -w` capture, sourced verbatim from Phase 11b's As-Built (Run 2, `docs/specs/phase-11b-failfast-and-vpa-verification.md:257-303` — the VPA-corrected-request run that actually scaled `2→3`, not Run 1's sub-threshold baseline), not re-run.
- `docs/evidence/replicas-vs-load-chart.svg` (or an alternative format, pending Open Question 3) — a chart of replica count over time correlated with CPU utilization, built from the same Run 2 (and, for contrast, Run 1) data points already captured in that As-Built.
- `docs/RUBRIC-CHECKLIST.md` line 90's evidence column updated to cite these two new files directly, alongside the existing As-Built citation — not a Deliverable of this spec/Plan commit; happens at As-Built time, per `docs/WORKFLOW.md` step 10.

## Non-goals
- No new load test, no new k3d cluster run, unless Open Question 1 is decided that way — the default assumption is reuse, not re-derivation.
- No new HPA/VPA analysis or conclusions beyond what Phase 11b's As-Built already states — this phase packages evidence, it doesn't produce new findings.
- No change to `k8s/base/hpa.yaml`/`vpa.yaml`/`backend.yaml` — those are Phase 11b's committed, real state; nothing here touches manifests.
- No pursuit of the other three §5.7 evidence items ("protection, conflict, blocked merge") — `docs/evidence/branch-protection.png` and the CI red/green screenshots already exist; a real two-author merge-conflict screenshot remains a separate, already-tracked gap (`docs/RUBRIC-CHECKLIST.md` line 11) and is out of scope here.
- No new dependency added to `backend/pyproject.toml` or anywhere else in the committed app just to plot a chart — confirmed directly that `matplotlib`/`pandas`/`plotly` are not installed in this environment and are not project dependencies anywhere; if a plotted-image chart is wanted (Open Question 3), it's produced without adding a runtime/dev dependency to the graded application, or the decision to add one is made explicitly, not silently.

## Open Questions

**1. Reuse Phase 11b's data, or run a fresh live load test?**
A real, hard constraint discovered while drafting this spec, not a preference: this session's shell cannot reach the Docker daemon (`docker ps` → `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`) — the same persistent environment gap disclosed repeatedly during Phase 13's compose work. `k3d`, `kubectl`, and `k6` binaries are all present on `PATH` (confirmed: `k3d version v5.9.0`, real `kubectl`/`k6` binaries found), but `k3d cluster create` provisions its nodes as Docker containers — it cannot run without daemon access. A fresh live run is therefore not achievable from inside this session regardless of preference; it would need to happen on a machine (or with a permission fix) outside this session, the same way Phase 13's real quickstart re-verification ultimately did.
**Recommendation:** reuse Phase 11b's real Run 2 data (and Run 1 for contrast) as the source for both files. It's real, already fully verified, already cited by `docs/DEMO-SCRIPT.md` Scene 5 and `docs/RUBRIC-CHECKLIST.md` line 90, and turning it into durable files doesn't require re-deriving anything. If a genuinely fresh run is wanted instead — to reconfirm the numbers still reproduce, or because Docker access exists on a machine I don't have — say so, and this phase's Plan runs the same 5-step loop again, live, before writing the files.

**2. `kubectl get hpa -w` — an actual screenshot image, or a plain text capture file?**
The assignment's §5.7 comment says "screenshots"; §5.8 item 6 says "capture," which is looser. This session has no browser or screenshot capability (confirmed repeatedly across every prior phase touching this limitation) — a `.png` screenshot of a terminal window can't be produced from here.
**Recommendation:** `docs/evidence/hpa-scaling.txt` — a plain-text file containing Phase 11b's real `kubectl get hpa -w` output verbatim (Run 2's `2→3` scale-out and scale-down sequences), with a one-line header citing exactly where it came from. If an actual screenshot image is wanted instead — e.g. because a grader expects `.png` specifically, matching the other evidence files' format — that needs to be captured on a machine with a real terminal and Docker access, the same way `docs/evidence/ci-red-blocked-merge.png` was captured after the fact from real Actions-run state. Either way this gets disclosed as text-only (or image, if produced) in the As-Built, not silently relabeled.

**3. What produces the "chart" — a plotted image, or a data table?**
No charting library is installed anywhere in this repo (confirmed: no `matplotlib`/`pandas`/`plotly` in `backend/pyproject.toml`; `import matplotlib` fails in this environment) and the project's tech stack doesn't call for one — adding one now purely to render one static image for `docs/evidence/` would be a new dependency for a single one-off artifact, against this project's "no dependencies beyond an approved phase's stated scope" rule.
**Recommendation:** hand-write a small SVG chart (`docs/evidence/replicas-vs-load-chart.svg`) plotting Run 2's real `(t, cpu%, replicas)` points directly as SVG markup — no new package, still a genuine visual chart, opens like any other image. The zero-dependency alternative (a plain Markdown/CSV table of the same real numbers) is equally honest but isn't really a "chart" the way the assignment names it. Say so if `matplotlib` should be added instead for a conventionally-plotted PNG, or if a table is actually acceptable.

## Plan
Not started — pending decisions on the three Open Questions above, per `docs/WORKFLOW.md` step 4 (the Plan is drafted and approved only after the spec itself is approved).

## Verification required
Not yet defined — depends on the Plan, which depends on the Open Questions above.

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md`, the assignment's §5.7/§5.8 text, or is underspecified beyond what's captured in the Open Questions above, stop and ask — do not silently resolve.

## As-Built
_Filled in after implementation._
