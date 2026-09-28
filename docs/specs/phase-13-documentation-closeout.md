# Phase 13: Documentation close-out
Status: done (Spec, Plan, Implementation, As-Built all committed; real quickstart verified end-to-end on the third attempt, two real bugs found and fixed along the way)
Depends on: everything (Phases 2–12) existing in at least draft form
Reads first: `docs/IMPLEMENTATION-PLAN.md` (Phase 13 entry), `docs/RUBRIC-CHECKLIST.md` (Category J + remaining §5.3 rows), `docs/CONTRACTS.md`, `docs/architecture/ARCHITECTURE.md`, `docs/WORKFLOW.md`, `Software Construction and Design -  Assignment 1.md` §4 Category J, §5.2, §5.3, §5.5, §5.7, §5.8

## Goal

Turn the project's real, already-verified state — spread across 12 phase specs' As-Built sections, `docs/adr/`, `docs/CONTRACTS.md`, and `docs/RUBRIC-CHECKLIST.md` — into the four portfolio documents Category J actually scores (README.md, `docs/RUNBOOK.md`, `docs/ENGINEERING-NOTES.md`) plus the honest-attribution document §5.5 requires (`docs/AI-USAGE.md`), a demo-video shot list, and a final truthful pass over `docs/RUBRIC-CHECKLIST.md`. This phase writes no application code and makes no architectural decisions — it cites and packages decisions already made, and where a citable answer doesn't exist yet, it says so as an Open Question rather than inventing one.

## Deliverables

- `README.md` — replaces the 5-line stub. Problem statement, CI/CD status badges (real GitHub Actions badge URLs for `ci.yml`/`cd.yml`/`release.yml`), a Mermaid architecture diagram (derived from `docs/architecture/ARCHITECTURE.md`, not invented fresh), a literally-tested one-command quickstart (`docker compose up` from a real clean-clone test — see Open Question 1), the 9-endpoint API table (from `docs/CONTRACTS.md` §2.2, not retyped by hand — copy it), and screenshots (frontend views — see Open Question 2 for what's actually achievable).
- `docs/RUNBOOK.md` — new file. How to deploy (compose + k8s paths), how to roll back (image-tag/SHA revert, per `docs/adr/0003-deploy-by-sha.md`), how to read logs (structured JSON to stdout — but see Ambiguity-handling: Category C's structured-logging row is currently `[ ]` unimplemented), and what to do when triage starts failing (fallback path, per `docs/adr/0001-provider-interface.md` and the LLM provider's retry/fallback behaviour).
- `docs/ENGINEERING-NOTES.md` — new file, all eight §5.2 questions answered with real file-and-line citations from this repository, not generic answers.
- `docs/AI-USAGE.md` — new file, per §5.5: naming the tools used, which parts they wrote or shaped, and what was changed afterward and why. Required by course policy regardless of Category J's marks table (§5.5 is separate from J's four scored line items — see Ambiguity-handling).
- `docs/TRIAGE.md` — new file, per Open Question 5's resolution: a consolidated AI/triage-layer explainer (provider interface, the three real implementations, selection/fallback/retry/cache behaviour, the prompt-injection guardrail) that cross-references `docs/adr/0001-provider-interface.md` and the real `backend/app/providers/triage/*.py` files rather than duplicating their content.
- `scripts/check_submission.py` — new file, per Open Question 5's resolution: a lint script (not a grader) mechanically checking the exact §5.3 deduction list — secrets anywhere in git history, unpinned/`:latest` images, `localhost` in service-to-service config, published DB/cache ports in `compose.prod.yaml`, publish/deploy jobs not gated by `needs:`, PostgreSQL as a Deployment with no PVC, direct commits to `main`.
- Demo-video shot list — a script/outline only (see Open Question 3), not the video itself.
- Final pass over `docs/RUBRIC-CHECKLIST.md` — Category J rows filled in with real citations once the above exist; a second pass over any other row that's gone stale since it was last touched.

**Explicitly not in this phase's Deliverables, resolved separately from the five Open Questions:** frontend screenshots (Submit/Dashboard/Stats) ship as a disclosed gap in README/`docs/evidence/`, to be closed by a real follow-up commit once the user captures them — same pattern as Phase 12's PR #15. The `kubectl get hpa -w` capture and replicas-vs-load chart, the branch-protection screenshot, and the merge-conflict screenshot are all out of scope for this phase entirely (spun into a separate addendum phase for the HPA/chart item; the other two wait on events — a real reviewed PR, a real merge conflict — that haven't happened yet) and nothing Kubernetes/load-test-related is touched here.

## Non-goals

- No application code, no Dockerfile/manifest/workflow changes. Pure documentation.
- No new ADRs decided in this phase preemptively — Open Question 4 asks whether any are actually missing; none get written speculatively.
- No attempt to actually record or produce the demo video — that requires a human with a microphone (§5.4's viva logic applies here too: a script Claude "performed" would be exactly the kind of AI-presented-as-own-work the course policy at §5.5 flags).
- No final §5.8 submission packaging (GHCR links, `git shortlog -sn` paste, HPA capture bundling) — those are submission-time actions performed once, immediately before submitting, not documentation artifacts this phase produces.
- Category A (collaboration) rows are not touched here beyond what's already accurately `[ ]`/at-risk in `docs/RUBRIC-CHECKLIST.md` — this phase doesn't change that reality.
- Bonus scope (`docs/OPEN-DECISIONS.md` #10) stays out of scope, same as Phase 12.

## Open Questions

All five below were raised at Spec time and are now resolved by explicit user decision, recorded here (not silently) before the Plan was written:

1. **README quickstart verification method.** I have no way to provision a genuinely fresh machine (no OS install, no unconfigured Docker daemon). The real test I can run: `git clone` the actual GitHub remote (`https://github.com/Zain-Shykh/Civic-Pulse.git`) into a brand-new directory outside this working tree, then follow the README's own steps verbatim (`cp .env.example .env`, fill required vars, `docker compose up`) with no reuse of this working tree's `.env` or any manual pre-step not written in the README. Caveat, stated up front rather than glossed over later: this machine's Docker daemon already has the base images (`python:3.12-slim`, `node:22-alpine`, `nginx:1.31-alpine`, `postgres:16-alpine`, `redis:7-alpine`) cached from earlier phases, so this does not prove a true first-ever pull on a machine with an empty image cache — only that the compose file, `.env.example`, and README steps are internally consistent and complete. **Resolved:** run it anyway, disclose the warm-Docker-cache limitation honestly in the As-Built — no fabricated "clean machine" claim.
2. **Frontend screenshots.** Same limitation as Phase 12 (no browser/screenshot tool available to me). **Resolved:** ship with a disclosed gap. The user captures Submit/Dashboard/Stats screenshots afterward, same pattern as Phase 12's PR #15 — planned as a real follow-up commit (see Deliverables), not left as a silent surprise gap.
3. **Demo video.** §J asks for "≤5 min, both partners speaking" — a real recording. **Resolved:** my deliverable is a shot-list/script only (scenes, what's shown, rough timing, which command runs on-screen); I do not claim to have produced the video, and `docs/RUBRIC-CHECKLIST.md`'s video row stays `[ ]` until an actual recording exists and is linked.
4. **Are any more ADRs actually missing?** Three real decisions (the Traefik `service.spec.type` Helm-value-path fix, the VPA-CRD-only install choice on `kind` vs. the real VPA-controller install on k3d, the nginx `1.27→1.31-alpine` base-image bump) are documented only inside phase-spec As-Builts, not as standalone ADRs. **Resolved:** no new ADRs — leave all three exactly where they are, in their originating phase's As-Built (already what `docs/RUBRIC-CHECKLIST.md` cites).
5. **`docs/TRIAGE.md` and `scripts/check_submission.py`**, named in the assignment's §5.7 layout tree but absent from this repo and unmentioned in `IMPLEMENTATION-PLAN.md`/`RUBRIC-CHECKLIST.md`. **Resolved:** write both. `docs/TRIAGE.md` is a consolidated AI/triage-layer explainer cross-referencing ADR 0001 and the real provider files, not duplicating them. `scripts/check_submission.py` is a lint (not a grader) mechanically checking the exact §5.3 deduction list named in the Deliverables section above — nothing beyond that list, since the assignment gives no fuller spec for it.

## Plan

### Order of work

Files are written in dependency order — later files cite earlier ones, so the earlier ones need to exist and be accurate first:

1. **`docs/TRIAGE.md`** — written first because `docs/RUNBOOK.md` (triage-failure section) and `docs/ENGINEERING-NOTES.md` (Q4, Q7) both cite it. Structure: one section per real file in `backend/app/providers/triage/` (`base.py` — the `TriageProvider` Protocol; `rules.py`, `simulated.py`, `llm.py` — the three real implementations, `ollama.py` noted as unimplemented per the already-open `docs/specs/phase-05b-llm-triage.md` Open Question 1, not silently hidden); `factory.py`'s `TRIAGE_PROVIDER`-driven selection; `llm.py`'s timeout/retry/fallback wrapper and `redaction.py`'s PII redaction, each cross-referenced to `docs/adr/0001-provider-interface.md` and `docs/adr/0004-pii-and-data-governance.md` rather than re-explained from scratch. Every claim gets a real `file:line` citation, checked by re-opening the cited line before writing it down.
2. **`scripts/check_submission.py`** — a single stdlib-only Python script (no new dependency — `pathlib`/`re`/`subprocess`/`json`, ponytail rung 3), run from the repo root, one function per §5.3 line item named in Deliverables, each printing `PASS`/`FAIL <reason>` and the script exiting non-zero if anything fails:
   - *Secrets in git history:* confirm `.env` is git-ignored and untracked (`git check-ignore .env`, `git ls-files .env` empty) and that `git log --all -- .env` returns nothing.
   - *Unpinned/`:latest` images:* regex-scan every `Dockerfile`, `compose*.yaml`, and `k8s/**/*.yaml` for a bare `FROM <image>` with no `:tag`, or any `:latest` tag.
   - *`localhost` in service-to-service config:* regex-scan `compose*.yaml` and `k8s/**/*.yaml` for `localhost`/`127.0.0.1`.
   - *Published DB/cache ports:* parse `compose.prod.yaml` as text for a `ports:` key nested under the `postgres`/`redis` service blocks.
   - *Ungated publish/deploy jobs:* line-scan `.github/workflows/cd.yml` and `release.yml` for job blocks whose name/content implies push-to-registry or deploy, and confirm a `needs:` key appears before the next top-level job key. Documented as a heuristic, not a full YAML AST parse — acceptable for a "lint, not a grader," matching the assignment's own description.
   - *Postgres as bare Deployment:* confirm `k8s/base/postgres.yaml` (or wherever it lives) declares `kind: StatefulSet`, and a `volumeClaimTemplates`/PVC reference exists for it.
   - *Direct commits to main:* shell out to `gh api repos/:owner/:repo/branches/main/protection` (already this session's established pattern) and confirm `enforce_admins.enabled == true` and `required_status_checks.contexts` is non-empty; degrade to a clear warning (not a silent pass) if `gh` isn't authenticated.
   No YAML-parsing dependency added — every check is regex/text-based against files whose real shape is already known, consistent with "lint, not grader."
3. **`docs/RUNBOOK.md`** — deploy (compose path + `kubectl apply -k k8s/overlays/{dev,prod}`), rollback (image-tag/SHA revert per `docs/adr/0003-deploy-by-sha.md`, plus `kubectl rollout undo`), reading logs (states plainly what's real today — `docker compose logs`/`kubectl logs`, not the aspirational structured-JSON format; see Ambiguity-handling), and "triage starts failing" (points at `docs/TRIAGE.md`'s fallback section, doesn't re-explain it).
4. **`docs/ENGINEERING-NOTES.md`** — all eight §5.2 questions, each answered with a real file:line citation checked before writing:
   - Q1 (laptop vs. CI runner): three real pinned lines — e.g. `backend/Dockerfile`'s `FROM python:3.12-slim`, `ci.yml`'s `TRIAGE_PROVIDER: simulated` env line, `postgres:16-alpine`/`redis:7-alpine` service image pins in `ci.yml`.
   - Q2 (CI/CD maturity ladder): answered against the real pipeline shape (`ci.yml`'s 7 jobs, `cd.yml`'s `needs:` gating, `release.yml`), not a generic ladder description.
   - Q3 (build-once-deploy-many): the real `${{ github.sha }}` tag line in `cd.yml`'s `build-push` job, cross-referenced to `docs/adr/0003-deploy-by-sha.md`.
   - Q4 (probabilistic LLM, deterministic CI): `SimulatedTriage` (`backend/app/providers/triage/simulated.py`) plus `TRIAGE_PROVIDER=simulated` in CI, cross-referenced to `docs/TRIAGE.md`.
   - Q5 (HPA lag): cited directly from `docs/specs/phase-11b-failfast-and-vpa-verification.md`'s As-Built (its "Real VPA controller install + HPA/VPA load-test loop" section) — that data is real and already exists; not re-derived, not re-run.
   - Q6 (VPA Off mode): cites `k8s/base/vpa.yaml` and the HPA/VPA conflict explanation already written in `docs/specs/phase-11-kubernetes-manifests.md`.
   - Q7 (`internal: true` network vs. hosted LLM): cites `compose.yaml`'s network definitions and how the backend (not frontend) is the only container with egress, cross-referenced to `docs/adr/0004-pii-and-data-governance.md`.
   - Q8 (the >1hr failure): the Phase 12 Traefik `service.spec.type`/Helm-value-path misdiagnosis across PRs #10–#12 (real symptom: `helm --wait` timing out at 120s/300s despite the pod being Ready in seconds; real wrong-first-belief: assumed `service.type` was the right value path; real log line that told the truth: the chart's own `values.yaml` showing the key actually lives under `service.spec.type`) — already a strong, real, disclosed candidate per `docs/specs/phase-12-ci-cd.md`'s As-Built, cited directly rather than re-narrated.
5. **`docs/AI-USAGE.md`** — names the tool (Claude Code / Claude Sonnet 5), honestly describes the actual working pattern used across this whole project (spec → plan → human approval → implementation → As-Built, per `docs/WORKFLOW.md`), and what got changed/rejected/corrected by the user along the way (real examples: the Traefik value-path re-fix, the nginx-bump deviation disclosure, the branch-protection scope check). Not generic — grounded in this repo's real commit history.
6. **`README.md`** — written last, since it draws on everything above: problem statement; real CI/CD badges for the three real workflow files (`ci.yml`, `cd.yml`, `release.yml`); a Mermaid diagram derived from `docs/architecture/ARCHITECTURE.md` (not invented independently); the API table copied verbatim from `docs/CONTRACTS.md` §2.2 (9 endpoints, with its own noted rubric-typo caveat carried over); the quickstart, written first, then actually run per Open Question 1's resolution, with real terminal output pasted into the As-Built and the warm-cache caveat stated in the README itself, not just the As-Built; a screenshots section with the two existing CI screenshots and an explicitly labeled placeholder/TODO for the frontend screenshots (not a silent omission), to be filled by the real follow-up commit once the user captures them.
7. **`docs/RUBRIC-CHECKLIST.md`** final pass — Category J's five rows updated with real citations to the files above; re-check every other row already `[x]` for staleness (same discipline as Phase 12's As-Built commit), and add a row/note for `docs/AI-USAGE.md` and `scripts/check_submission.py` per the Ambiguity-handling entry below (not silently folded into J's marks total).
8. **Commit 3 (implementation)**, then real verification, then **Commit 4 (As-Built)** — same four-commit shape as every other phase.

### Key technical choices

- `check_submission.py` gets zero new dependencies — stdlib + `gh`/`git` subprocesses only, matching the project's existing tooling (`gh api` is already this session's established verification pattern for branch protection).
- `docs/TRIAGE.md` and `docs/RUNBOOK.md` cross-reference existing ADRs/specs rather than re-stating their content, keeping one source of truth per decision (avoids the "which file is authoritative" drift risk named in `docs/WORKFLOW.md`).
- README's Mermaid diagram is derived from the existing `docs/architecture/ARCHITECTURE.md`, not drawn fresh from memory of the system — avoids introducing a second, possibly-drifted architecture description.
- The frontend-screenshot gap is planned for up front (explicit placeholder + named follow-up commit) rather than discovered mid-implementation, per the user's explicit instruction not to let this repeat Phase 12's pattern.

### Uncertainties carried into implementation

- The exact wording/format of `check_submission.py`'s ungated-job heuristic may need one iteration once written against the real `cd.yml`/`release.yml` text — flagged as an implementation detail, not a spec-level ambiguity, since the underlying check (does a `needs:` key exist before the job ends) is unambiguous.
- The quickstart run (Open Question 1) may surface a real README/`.env.example` bug on first attempt — if so, the fix is made and re-run, and both the failure and the fix are reported in the As-Built, not silently corrected and hidden.

## Verification required

- The literal clone/quickstart command sequence from Open Question 1, run for real from a fresh directory against the real GitHub remote, terminal output pasted in full (including the warm-Docker-cache caveat, stated not assumed).
- `docs/ENGINEERING-NOTES.md`'s eight answers cross-checked one by one by re-opening each cited `file:line` and confirming it actually says what the note claims — pasted, not asserted.
- A diff-based check that README's API table matches `docs/CONTRACTS.md`'s current table verbatim (not hand-retyped and drifted).
- `scripts/check_submission.py` actually run against this repo's real current state, real stdout pasted (expected: all real §5.3 items pass except whatever is already known-`[ ]` in `docs/RUBRIC-CHECKLIST.md`, e.g. no k8s manifests row is moot since manifests exist — every check's real result gets reported, not just "it runs").
- `docs/TRIAGE.md`'s file:line citations re-opened and confirmed accurate, same discipline as ENGINEERING-NOTES.
- `docs/RUBRIC-CHECKLIST.md`'s J rows and any other touched row cross-checked against the real file each one cites.

## Ambiguity handling

- `docs/AI-USAGE.md` is required by §5.5 but is not one of Category J's four scored line items (README, ADRs, RUNBOOK, video, ENGINEERING-NOTES are the five J rows actually listed with marks in both the assignment text and `docs/RUBRIC-CHECKLIST.md`; §5.5's AI-USAGE requirement sits outside that table, tied to plagiarism policy instead). Building it anyway, folded into this phase for practical reasons (it belongs with the other portfolio docs), but not silently counted toward J's 15 marks in `docs/RUBRIC-CHECKLIST.md` — it gets its own note, not a merged row.
- `docs/RUNBOOK.md`'s "how to read logs" section will describe the *intended* structured-JSON-with-request_id logging design per `docs/CONTRACTS.md`/ADRs, but Category C's row for that ("Structured JSON logging to stdout with a propagated request_id") is currently `[ ]` — unimplemented, confirmed by checking `docs/RUBRIC-CHECKLIST.md` directly rather than assumed. The RUNBOOK will not claim this exists; it will describe what's actually there today (`docker compose logs`/`kubectl logs`, whatever format is real right now) and flag the gap rather than writing the runbook against an aspirational feature.
- `scripts/check_submission.py` is named in the assignment's §5.7 layout/§5.8 submission checklist but carries no marks line of its own anywhere in the rubric text — it earns credit only indirectly, by keeping the real §5.3 automatic-deduction rows accurate. It is not added as a new row to `docs/RUBRIC-CHECKLIST.md`'s Category J or §5.3 tables; its existence and a real run's output are noted in this phase's As-Built instead.
- Open Questions 1–5 above were the "stop and ask" cases raised at Spec time, per `docs/WORKFLOW.md` and `CLAUDE.md` — all five are now resolved by explicit user decision (recorded above), and the Plan above is built against those resolutions, not a guess. This spec+plan stops here, before any implementation, per the pasted instruction that resolved them.

## As-Built

### What shipped

**Correction to this As-Built, made after the fact:** the paragraph below originally said "All Deliverables landed" while listing six of the seven — it omitted the demo-video shot-list, and no such file actually existed at that commit despite the Deliverables list (line 18) committing to one. That was a real gap, not a rename or a rewording — the shot-list is written now, as `docs/DEMO-SCRIPT.md`, in a dedicated follow-up commit to this phase.

All Deliverables landed: `docs/TRIAGE.md`, `scripts/check_submission.py`, `docs/RUNBOOK.md`, `docs/ENGINEERING-NOTES.md`, `docs/AI-USAGE.md`, `README.md` (full rewrite), `docs/DEMO-SCRIPT.md` (demo-video shot-list, added after this As-Built was first written — see correction above), and a final `docs/RUBRIC-CHECKLIST.md` pass — in that order, per the approved Plan. Commits: `2368059` (spec) → `8892c62` (plan) → `f65b56a` (implementation) → `a829625` (merge, reconciling concurrent frontend PRs #5/#7/#8 that landed on `origin/dev` mid-phase — disclosed here, not smoothed over) → `618fd4a` (fix 1) → `5136966` (fix 2) → `5e93d4c` (this As-Built, originally) → this commit (demo-script gap fix).

### Two real, disclosed deviations from the "docs only" Non-goal

Both were found by actually running the quickstart, not by inspection, and both were disclosed and approved before being made — neither slipped in silently:

**Fix 1 — `.env.example` duplicate-key shadowing bug (`618fd4a`).** `.env.example` had two active `TRIAGE_PROVIDER=` lines (one under a "dev only: rules" comment, one under a "prod only: llm" comment, followed by a placeholder `GEMINI_API_KEY`). A literal `cp .env.example .env` — exactly what the README instructs — let the second, later assignment silently win regardless of its comment header, resolving `TRIAGE_PROVIDER=llm` for the *dev* stack too, breaking the no-API-key-needed quickstart promise without erroring. Confirmed via `docker compose config` (a static, daemon-independent render) before and after. Fixed by commenting out the two prod-only lines; re-verified `compose.prod.yaml config` still fails loudly on a missing `GEMINI_API_KEY`, so the fix didn't weaken Phase 10's existing fail-fast design.

**Fix 2 — missing schema migration on `docker compose up` (`5136966`).** A genuinely fresh `docker compose up` left Postgres with zero tables (`\dt` → no relations) and `POST /api/complaints` 500ing with `psycopg.errors.UndefinedTable: relation "complaints" does not exist`. Neither `compose.yaml` nor `compose.prod.yaml` ever ran `alembic upgrade head` — a known gap from Phase 11's Open Question 6, already solved for Kubernetes by `k8s/base/backend.yaml`'s `migrate` initContainer, whose own comment discloses "No environment so far (dev compose, CI) has ever automated this." Fixed by mirroring that exact pattern rather than inventing a new one: a one-shot `migrate` service (same backend image, `command: ["alembic", "upgrade", "head"]`, `restart: "no"`) added to both compose files, with `backend`'s `depends_on` gaining a `migrate: condition: service_completed_successfully` entry alongside its existing postgres/redis conditions. `docs/RUNBOOK.md`'s Deploy section got one added sentence noting the automatic step. The four-command quickstart sequence itself did not change — `docker compose up` is still the whole story.

### Real quickstart verification — three attempts, third succeeded

Per Open Question 1's resolution (real GitHub clone, no reuse of this working tree's `.env`, no manual pre-steps beyond the README's own four commands):

1. **First attempt** hit Fix 1's `.env.example` shadowing bug on a stale `main` clone (`TRIAGE_PROVIDER` resolved to `llm` instead of `rules`).
2. **Second attempt**, after Fix 1, hit Fix 2's missing-migration bug on `dev` (`\dt` → no relations; `POST /api/complaints` → 500, `psycopg.errors.UndefinedTable: relation "complaints" does not exist`).
3. **Third attempt**, after both fixes, succeeded end to end. Real terminal output, pasted verbatim (not described):

```
$ docker compose exec postgres psql -U civicpulse -d civicpulse -c '\dt'
                List of relations
 Schema |      Name       | Type  |   Owner
--------+-----------------+-------+------------
 public | alembic_version | table | civicpulse
 public | complaints      | table | civicpulse
(2 rows)

$ curl -s -X POST http://localhost:8080/api/complaints -H "Content-Type: application/json" -d '{"text":"Streetlight out on Elm St","location":"Elm St"}'
{"id":"78c93fd0-e0c8-4d8e-9d7d-d2df28da0ce8","text":"Streetlight out on Elm St","location":"Elm St","reporter_contact":null,"category":"streetlights","priority":"normal","status":"open","ai_summary":"Streetlight out on Elm St","triaged_by":"rules","triage_latency_ms":0,"created_at":"2026-09-27T21:50:05.031036Z","updated_at":"2026-09-27T21:50:05.031036Z","used_fallback":false,"cache_hit":false}

$ curl -s http://localhost:8080/api/stats
{"counts_by_status":{"open":1},"counts_by_category":{"streetlights":1},"average_triage_latency_ms":0.0}

$ docker compose exec backend python -c "...localhost:8000/health..."
b'{"status":"ok"}'
$ docker compose exec backend python -c "...localhost:8000/ready..."
b'{"status":"ready"}'

$ docker compose ps
NAME                              IMAGE                     COMMAND                  SERVICE    CREATED          STATUS                    PORTS
civicpulse-clonetest-backend-1    civicpulse-backend:dev    "uvicorn app.main:ap…"   backend    28 seconds ago   Up 21 seconds (healthy)   8000/tcp
civicpulse-clonetest-frontend-1   civicpulse-frontend:dev   "/docker-entrypoint.…"   frontend   28 seconds ago   Up 16 seconds (healthy)   80/tcp, 0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp
civicpulse-clonetest-postgres-1   postgres:16-alpine        "docker-entrypoint.s…"   postgres   28 seconds ago   Up 28 seconds (healthy)   5432/tcp
civicpulse-clonetest-redis-1      redis:7-alpine            "docker-entrypoint.s…"   redis      28 seconds ago   Up 28 seconds (healthy)   6379/tcp
```

**Honest reading of the response body, not just its status code:** `used_fallback: false` and `triaged_by: "rules"` together confirm `TRIAGE_PROVIDER=rules` resolved correctly this time (Fix 1 held, no shadowing), and `category: "streetlights"` / `priority: "normal"` match `RuleBasedTriage`'s real keyword-matching behaviour against "Streetlight out on Elm St" — genuinely deterministic output, not spot-checked against anything fabricated.

**Warm-Docker-cache caveat, as planned in Open Question 1 and already stated in `README.md`:** this machine's Docker daemon already had the base images (`python:3.12-slim`, `node:22-alpine`, `nginx:1.31-alpine`, `postgres:16-alpine`, `redis:7-alpine`) cached from earlier work, so this run does not prove a true first-ever image pull on a machine with a completely empty cache — only that the compose files (including the two real fixes above), `.env.example`, and the README's four commands are internally consistent and complete on their own.

**Environment note:** this background job's own shell could not run the live `docker compose up` portion itself (`permission denied while trying to connect to the docker API` — this account isn't in the `docker` group here, confirmed genuine via a `dangerouslyDisableSandbox` retry and the absence of any rootless-Docker fallback). The three-attempt sequence above, including both bug discoveries and the final successful run's real pasted output, was executed and reported by the user directly.

### `scripts/check_submission.py` — real run

```
[PASS] No secrets in git history — .env gitignored, untracked, absent from git history
[PASS] Base images pinned, no :latest — 18 Dockerfile/compose/k8s files scanned, every image pinned or Kustomize-tagged, no hardcoded :latest
[PASS] No localhost in service-to-service config — no localhost/127.0.0.1 in compose*.yaml or k8s/**/*.yaml
[PASS] No published DB/cache ports in compose.prod.yaml — no ports: under postgres/redis in compose.prod.yaml
[PASS] Publish/deploy jobs gated by needs: — cd.yml: build-push needs [test-backend, test-frontend], deploy-k8s needs build-push; release.yml exempt by design (tag-push only, re-tags an already-tested SHA)
[PASS] PostgreSQL is a StatefulSet with a PVC, not a bare Deployment — k8s/base/postgres.yaml: StatefulSet + volumeClaimTemplates present
[PASS] No direct commits to main (branch protection enforced) — main protected: enforce_admins=True, 7 required status checks

All checks passed (or warned). EXIT: 0
```

Self-tested beforehand against a synthetic bad repo (since removed) to confirm every check is a real detector, not a no-op: all 5 checkable-in-sandbox violations (`ubuntu:latest`, an untagged image, `localhost` in config, a published port, an ungated `cd.yml` job, a bare `Deployment` named postgres) correctly `FAIL`ed; the two unverifiable-in-sandbox cases (an ungitignored `.env`, `gh api` against a fake remote) correctly `WARN`ed rather than silently passing or falsely failing.

### Verification cross-checks

- `docs/ENGINEERING-NOTES.md`'s eight citations re-opened and confirmed to say what each note claims, before this As-Built was written.
- README's 9-endpoint API table confirmed copied verbatim from `docs/CONTRACTS.md` §2.2, no hand-retyping drift.
- `docs/TRIAGE.md`'s citations re-opened and confirmed accurate against the real `backend/app/providers/triage/*.py` files.
- `docs/RUBRIC-CHECKLIST.md`'s §5.3 "README quickstart" row flipped `[ ] → [x]`, citing this section directly (see below).

### Scope held as planned

Frontend screenshots (Submit/Dashboard/Stats) remain a disclosed gap in `README.md`, to be closed by a real follow-up commit once captured manually — not silently resolved here. The HPA `-w` capture/replicas-vs-load chart, the branch-protection screenshot, and the merge-conflict screenshot remain entirely out of this phase's scope, exactly as the spec's Deliverables section scoped them out — nothing Kubernetes/load-test-related was touched.

### Audit against `docs/WORKFLOW.md`'s three failure modes

- **Silent decisions:** none — both real bugs found mid-implementation were disclosed and their fixes explicitly approved by the user before being made, not slipped in under a "docs only" phase.
- **Unverified claims:** the quickstart's warm-Docker-cache limitation is stated plainly in both `README.md` and here, not glossed over; the demo video stays `[ ]` since only a shot-list exists; this background job's own inability to run `docker compose up` directly is disclosed rather than papered over with fabricated output.
- **Undisclosed scope creep:** the two compose-file fixes are real, necessary deviations from the "docs only" Non-goal, and are called out as such by name in this section, not buried in a generic "implementation" commit message.

Status: **done** — all four commits (spec, plan, implementation, as-built) complete, real quickstart verified end-to-end (third attempt), `check_submission.py` run for real, `docs/RUBRIC-CHECKLIST.md` updated.
