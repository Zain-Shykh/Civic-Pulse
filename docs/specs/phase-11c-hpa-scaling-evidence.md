# Phase 11c: HPA/VPA scaling evidence capture
Status: done (spec, plan, implementation, and As-Built all landed per `docs/WORKFLOW.md`'s four-commit lifecycle — see Open Questions below for how the plan itself changed mid-flight)
Depends on: Phase 11b (`docs/specs/phase-11b-failfast-and-vpa-verification.md`) — same tuned `k8s/base/hpa.yaml`/`vpa.yaml` config and VPA-corrected request, but this phase's evidence comes from its own genuinely fresh live run, not reused Phase 11b data (see Open Question 1, resolved below).
Reads first: `docs/specs/phase-11b-failfast-and-vpa-verification.md`'s As-Built (real HPA/VPA numbers, lines 190–306); the assignment's §5.7 "Repository layout" (`docs/evidence/` comment: "screenshots: protection, conflict, blocked merge, hpa -w, scaling chart") and §5.8 "Submission" item 6 ("kubectl get hpa -w capture and your replicas-vs-load chart") verbatim; `docs/RUBRIC-CHECKLIST.md` line 90 (already `[x]`, citing Phase 11b's As-Built prose directly — this phase produces the durable file that row's evidence column currently lacks, not a re-derived analysis); `docs/DEMO-SCRIPT.md` Scene 5 (already cites the same Phase 11b data for the demo video).

This is not a phase from `docs/IMPLEMENTATION-PLAN.md`'s original sequence — added after Phase 11b shipped, same pattern as Phase 11b was to Phase 11 (and 9c to 9). `docs/IMPLEMENTATION-PLAN.md` gets a matching entry in the same commit as this spec.

## Goal
Produce the durable evidence files the assignment names and that currently don't exist anywhere in the repo: `kubectl get hpa -w` screenshots and a replicas-vs-load chart, both under `docs/evidence/`. This spec started from the assumption that Phase 11b's already-verified data (a `2→3` scale-out at 79–89% utilization, torn down afterward with no durable file ever committed) would have to be repackaged rather than re-derived, since this session's Docker daemon access was believed unavailable. That constraint was lifted mid-session, and a genuinely fresh k3d cluster was created and load-tested live instead — real screenshots exist as a result, not a text fallback. See Open Questions below for the full resolution and the real numbers this run actually produced.

## Deliverables
See "Deliverables — final" below the Open Questions — superseded by a real fresh live run partway through drafting this spec (see Open Question 1).

## Non-goals
- No new HPA/VPA analysis or conclusions beyond narrating this run's own real numbers — this phase packages evidence, it doesn't reopen Phase 11b's tuning decisions.
- No change to `k8s/base/hpa.yaml`/`vpa.yaml`/`backend.yaml` — those are Phase 11b's committed, real state; nothing here touches manifests.
- No pursuit of the other three §5.7 evidence items ("protection, conflict, blocked merge") — `docs/evidence/branch-protection.png` and the CI red/green screenshots already exist; a real two-author merge-conflict screenshot remains a separate, already-tracked gap (`docs/RUBRIC-CHECKLIST.md` line 11) and is out of scope here.
- No new dependency added to `backend/pyproject.toml` or anywhere else in the committed app just to plot a chart — confirmed directly that `matplotlib`/`pandas`/`plotly` are not installed in this environment and are not project dependencies anywhere; if a plotted-image chart is wanted (Open Question 3), it's produced without adding a runtime/dev dependency to the graded application, or the decision to add one is made explicitly, not silently.

## Open Questions — resolved

**1. Reuse Phase 11b's data, or run a fresh live load test? → Resolved: a fresh live run happened, mid-session, better than planned.**
This spec originally recorded, as a hard constraint, that this session's shell could not reach the Docker daemon, making a fresh k3d run impossible from here. That constraint was lifted mid-session (a `sg docker -c "<cmd>"` / `newgrp docker <<< "<cmd>"` group-switch wrapper was found to restore daemon access per-invocation — confirmed via real `docker ps`/`docker version` output). A genuinely fresh cluster was then created and load-tested live, not reused from Phase 11b. This produced different, real numbers from Phase 11b's Run 2 (`2→3` at 82%) — this run scaled `2→4`, peaking at **106%** utilization (both HPA-watch readings at the trigger moment read exactly `106%/60%`, not the `106–113%` range first reported verbally before the screenshots were reviewed directly — corrected here to what the captured evidence actually shows). This is a real, disclosed divergence from Phase 11b, not an inconsistency to paper over: same manifests (`k8s/base/hpa.yaml`/`vpa.yaml`, unchanged, per Non-goals), a different live run, achieving higher real concurrency against the same 60% CPU target and the same VPA-corrected 163m request, so it crossed the `4`-replica threshold instead of stopping at `3`. Full sequence in the As-Built below.

**2. `kubectl get hpa -w` — screenshot or text? → Resolved: real `.png` screenshots exist, no text-capture fallback needed.**
Three real screenshots landed on `dev` from the live run: `docs/evidence/hpa-scaling-idle.png`, `docs/evidence/hpa-scaling-scaleout.png`, `docs/evidence/hpa-scaling-scaledown.png` (43KB/71KB/210KB, terminal-captured, timestamped 2026-09-28 19:33/19:59/20:17). These directly satisfy §5.7's "screenshots" wording — no `.txt` fallback is needed, and the tentative `hpa-scaling.txt` Deliverable named below is dropped.

**3. What produces the "chart"? → Unchanged: hand-written SVG, no new dependency.**
Still the right call — no charting library is installed anywhere in this repo, and this project's "no dependency beyond an approved phase's stated scope" rule still applies. `docs/evidence/replicas-vs-load-chart.svg`, hand-written, plotting the real `(t, cpu%, replicas)` points read directly off the three screenshots above (not Phase 11b's numbers).

## Deliverables — final
- `docs/evidence/hpa-scaling-idle.png`, `docs/evidence/hpa-scaling-scaleout.png`, `docs/evidence/hpa-scaling-scaledown.png` — real screenshots, already present on `dev` (untracked pending this phase's implementation commit).
- `docs/evidence/replicas-vs-load-chart.svg` — hand-written, built from the real data points in the three screenshots above.
- `docs/RUBRIC-CHECKLIST.md` line 90's evidence column, updated to cite these four files directly (at As-Built time, per `docs/WORKFLOW.md` step 10).

## Plan
1. **`docs/evidence/replicas-vs-load-chart.svg`** (new file) — hand-written SVG, no dependency. Plots two series over the real ~22-minute window read directly off `hpa-scaling-scaleout.png`/`hpa-scaling-scaledown.png`: CPU utilization % (line) and replica count (step line), both against elapsed time since the watch started. Real marker points only — idle 2%/2 replicas, unknown%/2 replicas through 3m16s, `106%`/2→4 replicas at 4m1s–4m16s, plateau 55–63%/4 replicas from 12m–16m, drop 48%→41%→12%→2% at 17m, held 2%/4 replicas 17m–21m (~5min, matching the tuned 300s `scaleDown.stabilizationWindowSeconds`), step-down 4→3→2 at 22m. No interpolated data invented between real readings beyond straight-line connectors between actual captured points.
2. **`docs/RUBRIC-CHECKLIST.md`** — line 90's evidence column gets the four new file citations appended, alongside the existing Phase 11b As-Built citation (which stays — it's still the source of the tuned-behavior config and the required lag writeup).
3. **This spec's own As-Built** — filled in with the real screenshot content (transcribed directly, not summarized) and the real job-completion/max-pods-fix facts reported directly, both from this session's own live run.
4. Not touched: `k8s/base/hpa.yaml`/`vpa.yaml`/`backend.yaml` (unchanged, per Non-goals), `docs/DEMO-SCRIPT.md` Scene 5 (still cites Phase 11b's `2→3`/82% numbers — now one run behind the fresher `2→4`/106% evidence this phase produced; flagged in the As-Built as an open item for a separate decision, not silently updated here since it's outside this spec's Deliverables).

## Verification required
- Read all three `.png` files directly and transcribe their real on-screen content into the As-Built (not paraphrased from memory).
- Confirm `docs/evidence/replicas-vs-load-chart.svg` renders as valid SVG and its plotted points match the screenshots' real numbers exactly.
- `git status`/`git diff --stat` after staging, to confirm only this phase's intended files are included.

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md`, the assignment's §5.7/§5.8 text, or is underspecified beyond what's captured in the Open Questions above, stop and ask — do not silently resolve.

## As-Built

**Status: done.** All four Deliverables committed: `docs/evidence/hpa-scaling-idle.png`, `docs/evidence/hpa-scaling-scaleout.png`, `docs/evidence/hpa-scaling-scaledown.png` (`cb93317`), `docs/evidence/replicas-vs-load-chart.svg` (`cb93317`), and `docs/RUBRIC-CHECKLIST.md` line 90's evidence column (`cb93317`).

**How the run happened, honestly:** this spec was drafted assuming reuse of Phase 11b's data was the only option, since this session's Docker daemon access was believed permanently blocked. Mid-session, the user supplied a working per-invocation workaround (`sg docker -c "<cmd>"` / `newgrp docker <<< "<cmd>"`), confirmed with real `docker ps` (empty container list, exit 0) and `docker version --format '{{.Server.Version}}'` → `29.8.0`. A fresh k3d cluster was then created and load-tested live — not a re-derivation of Phase 11b's numbers, a second, independent real run against the same tuned `k8s/base/hpa.yaml`/`vpa.yaml` config.

**Real deviation hit and fixed, same class as Phase 11b's own:** the fresh cluster's default kubelet `max-pods` (110) capped concurrent k6 Job pods below what the load test needed. Fixed by recreating the cluster with `--k3s-arg '--kubelet-arg=max-pods=500@server:0'`, confirmed via `kubectl get node -o jsonpath='{.items[0].status.allocatable.pods}'` returning `500` before retrying — this is a cluster-creation-time flag, not committed state, so it isn't reflected in any manifest.

**Real screenshot content, transcribed directly (not summarized) from each `.png`:**

`hpa-scaling-idle.png` — one-shot `kubectl get hpa -n civicpulse`:
```
NAME         REFERENCE            TARGETS    MINPODS   MAXPODS   REPLICAS   AGE
backend-hpa  Deployment/backend   cpu: 2%/60%   2         10        2       4m10s
```

`hpa-scaling-scaleout.png` — `kubectl get hpa -n civicpulse -w`:
```
NAME         REFERENCE            TARGETS              MINPODS  MAXPODS  REPLICAS  AGE
backend-hpa  Deployment/backend   cpu: <unknown>/60%      2        10        2      97s
backend-hpa  Deployment/backend   cpu: <unknown>/60%      2        10        2      2m31s
backend-hpa  Deployment/backend   cpu: <unknown>/60%      2        10        2      3m1s
backend-hpa  Deployment/backend   cpu: <unknown>/60%      2        10        2      3m16s
backend-hpa  Deployment/backend   cpu: 106%/60%           2        10        2      4m1s
backend-hpa  Deployment/backend   cpu: 106%/60%           2        10        4      4m16s
```
**Correction to the verbal summary that preceded this As-Built:** the peak utilization was reported as "106–113%" before the screenshots were reviewed directly. The actual captured evidence shows exactly `106%/60%` at both readings around the scale-out — there is no `113%` reading in the real capture. Corrected here rather than silently carried forward.

`hpa-scaling-scaledown.png` — continuation of the same `-w` session:
```
backend-hpa  cpu: 57%/60%  4  12m      backend-hpa  cpu: 58%/60%  4  14m      backend-hpa  cpu: 55%/60%  4  16m
backend-hpa  cpu: 60%/60%  4  12m      backend-hpa  cpu: 59%/60%  4  14m      backend-hpa  cpu: 59%/60%  4  16m
backend-hpa  cpu: 56%/60%  4  12m      backend-hpa  cpu: 60%/60%  4  14m      backend-hpa  cpu: 60%/60%  4  16m
backend-hpa  cpu: 59%/60%  4  13m      backend-hpa  cpu: 63%/60%  4  15m      backend-hpa  cpu: 56%/60%  4  16m
backend-hpa  cpu: 58%/60%  4  13m      backend-hpa  cpu: 56%/60%  4  15m      backend-hpa  cpu: 48%/60%  4  17m
backend-hpa  cpu: 57%/60%  4  13m      backend-hpa  cpu: 60%/60%  4  15m      backend-hpa  cpu: 41%/60%  4  17m
                                                                                backend-hpa  cpu: 12%/60%  4  17m
                                                                                backend-hpa  cpu: 2%/60%   4  17m
backend-hpa  cpu: 2%/60%  4  18m (x2)  backend-hpa  cpu: 2%/60%  4  19m  backend-hpa  cpu: 2%/60%  4  20m
backend-hpa  cpu: 2%/60%  4  21m (x2)  backend-hpa  cpu: 2%/60%  2  10  3  22m   backend-hpa  cpu: 2%/60%  2  10  2  22m
```
Plateau: 55–63% at 4 replicas from `12m` through `16m` (matches the user's own real-time narration: "held steady 55–63% at 4 replicas for several minutes"). Drop to 2% at `17m`. Held at 4 replicas from `17m` through `21m` — roughly 4–5 real minutes, consistent with the tuned `scaleDown.stabilizationWindowSeconds: 300`. Stepped down `4→3` then `3→2`, both readings recorded at the same rounded `22m` age — a fast but real two-step sequence, not an instant jump straight to `2`.

**Job completion and teardown**, reported as real command output by the user during this session (no separate screenshot file for these): `kubectl get job k6-load-test -n civicpulse` showed `450/450` completions, `Complete`, ~15 minutes duration, before the cluster was torn down; `docker ps -a` afterward showed no `civicpulse` containers remaining.

**Open item, not resolved here (outside this spec's Deliverables, flagged per Non-goals):** `docs/DEMO-SCRIPT.md` Scene 5 still cites Phase 11b's `2→3`/82% numbers, which are now one run behind this phase's fresher `2→4`/106% evidence. Whether Scene 5 should be updated to reference the newer screenshots, or intentionally left citing Phase 11b's data (both are real, either is defensible), is a call for the next session, not decided silently here.

**Audit against the three named failure modes:**
- *Silent decisions* — none: the daemon-access change, the max-pods refix, and the `106%` vs. `106–113%` correction are all disclosed above rather than folded in quietly.
- *Unverified claims* — the three screenshot transcriptions were read directly from the `.png` files, not recalled from the earlier chat narration; the job-completion/teardown facts are disclosed as reported (not independently re-verified by this agent), since no cluster remained to re-check them against.
- *Undisclosed scope creep* — none: `k8s/base/hpa.yaml`/`vpa.yaml`/`backend.yaml` untouched; `docs/DEMO-SCRIPT.md` deliberately left alone and flagged above rather than edited outside this spec's Deliverables.
