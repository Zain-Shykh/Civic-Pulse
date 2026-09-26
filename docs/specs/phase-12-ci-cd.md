# Phase 12: CI/CD
Status: not started
Depends on: Phase 5a (`SimulatedTriage`, needed for deterministic `ci.yml` test runs — no external network call, no rate-limit/quota risk on a shared CI runner); Phase 11 (`docs/specs/phase-11-kubernetes-manifests.md`) and Phase 11b (`docs/specs/phase-11b-failfast-and-vpa-verification.md`) for the manifests `cd.yml`'s `deploy-k8s` job applies.
Reads first: the assignment's §3.4 (CI/CD) verbatim, both job tables and the Non-negotiables list; `docs/IMPLEMENTATION-PLAN.md`'s Phase 12 entry; `docs/adr/0003-deploy-by-sha.md`; `docs/RUBRIC-CHECKLIST.md` Category I; `docs/CONTRACTS.md` (the `/api/stats` `X-Cache` header, `/health`/`/ready` split, `POST /api/complaints`); `.github/workflows/` (currently a single placeholder `README.md` — no workflow file exists yet); `k8s/overlays/prod/kustomization.yaml` (no `images:` transformer committed — per ADR 0003, this phase's `cd.yml` is the only writer of a real tag, via `kustomize edit set image`); `backend/tests/`, `frontend/tests/` (what `test-backend`/`test-frontend` actually run); `backend/pyproject.toml` (`ruff`/`mypy`/`pytest-cov` already configured as dev dependencies, but no `--cov-fail-under` gate wired anywhere yet); `frontend/package.json` (`lint`/`typecheck`/`test` scripts already exist: `eslint .`, `tsc -b --noEmit`, `vitest run`); both Dockerfiles (multi-stage, non-root, pinned base images — confirms what `build`/`scan` target); `compose.yaml` (dev shape: `frontend` publishes `8080`, `backend` publishes no host port at all, `TRIAGE_PROVIDER` read from env with no default); `frontend/nginx.conf` (proxies only `location /api/` to `backend:8000` — `/health`/`/ready` are unprefixed root paths on the backend, not under `/api/`, so they are **not** reachable through the published frontend port as currently configured — see Open Question 2).

This is Phase 12 from `docs/IMPLEMENTATION-PLAN.md`'s original sequence, not an inserted follow-up phase like 9c/11b.

## Goal
Build the three GitHub Actions workflows the assignment requires (§3.4, Rubric Category I) — `ci.yml` on PRs to `main` (and pushes to `dev`), `cd.yml` on push to `main`, `release.yml` on `v*` tags — covering the core 150-mark requirement set only. No bonus item (GitOps, digest pinning + Cosign, Prometheus/Grafana, OpenTelemetry, zero-downtime-under-load) is in scope here; `docs/OPEN-DECISIONS.md` #10 stays open past this phase (see the correction to that entry, committed alongside this spec).

## Deliverables

**`ci.yml`** — triggers: `pull_request` targeting `main`, `push` to `dev`. Jobs:
- `lint-and-type`: `ruff check` + `mypy` on the backend; `eslint .` + `tsc -b --noEmit` on the frontend (both scripts already exist in `frontend/package.json`).
- `test-backend`: `pytest` with `TRIAGE_PROVIDER=simulated`, coverage ≥65% on `app/` (`pytest-cov` already a dev dependency; the `--cov-fail-under=65` gate itself does not exist yet anywhere in `backend/pyproject.toml` — this job adds it). Needs live Postgres/Redis — run as GitHub Actions `services:` containers (Postgres 16, Redis 7, pinned, matching the versions already used everywhere else in this project), not the established local ephemeral-container-on-the-compose-network pattern, since that pattern exists specifically to avoid publishing host ports on a developer's machine — a CI runner has no such concern and `services:` is the standard-library-equivalent GitHub Actions mechanism for this.
- `test-frontend`: `vitest run` (already ≥5 test files exist: `api-client`, `Submit`, `Dashboard`, `Home`, `Stats` — this job wires them into CI, it does not write new ones).
- `build`: build both images from their Dockerfiles. No push — a PR must not publish artifacts (assignment's own explicit line).
- `scan`: Trivy against both built images, failing on HIGH/CRITICAL with a fix available.
- `manifests`: `kustomize build k8s/overlays/prod | kubeconform` (or equivalent) — catches a broken manifest before it ever reaches a cluster. See Open Question 3 for the CRD-schema risk this specific manifest set carries (the VPA object).
- `integration`: `docker compose up -d` (dev `compose.yaml`, `TRIAGE_PROVIDER=rules` — deterministic, no live LLM call, same reasoning as `test-backend`'s `simulated`), wait for readiness, `POST /api/complaints`, `GET` it back, assert the returned category, check `/api/stats`'s `X-Cache` header goes `MISS → HIT` on a repeat call, `docker compose down -v`. See Open Question 2 for how "wait for readiness" is actually reached given the nginx proxy's real shape, and Open Question 4 for teardown reliability.

All seven jobs configured as required checks on PRs to `main` (branch-protection *rule configuration* itself is a manual GitHub Settings/API action, not a file this phase commits — see Ambiguity handling).

**`cd.yml`** — trigger: `push` to `main`. Jobs, `needs:`-chained:
- `test` (no `needs:` — first job): the full suite again, on the merged result.
- `build-push` (`needs: test`): build both images, push to GHCR tagged `${{ github.sha }}` and `latest` (the SHA tag is the only one ever deployed — ADR 0003; `latest` is published for human browsing only). Emit an SBOM via Syft. Capture the image digest as a job output. GHCR image paths must be lowercase (`ghcr.io/<owner>/<image>`) — this repo's GitHub owner/name (`Zain-Shykh/Civic-Pulse`) contains uppercase letters, so the job must lowercase `github.repository` before using it in the image ref, not pass it through as-is (a real first-attempt failure otherwise, not a hypothetical one).
- `deploy-k8s` (`needs: build-push`): spin up an ephemeral cluster in the runner (tool choice: Open Question 1), `kustomize edit set image backend=... frontend=...` inside `k8s/overlays/prod` with the SHA tag (never hand-editing the committed file — ADR 0003), `kubectl apply -k`, wait on `kubectl rollout status`, smoke-test the Ingress, print `kubectl get hpa`.

**`release.yml`** — trigger: push of a `v*` tag. Build, push semver tags, generate release notes. Whether it re-runs tests itself: Open Question 5.

**Non-negotiables, wired directly into the above rather than treated as separate deliverables:**
- `needs:` gates every publish/deploy job (`build-push`, `deploy-k8s`, and `release.yml`'s publish step).
- `permissions:` block on every workflow, least-privilege — `contents: read` by default, `packages: write` added only on the job that actually pushes to GHCR.
- All credentials from GitHub Secrets; GHCR auth via the built-in scoped `GITHUB_TOKEN` with `packages: write`, not a personal account password or a long-lived PAT.
- Actions pinned to at least `@v4` (e.g. `actions/checkout@v4`, `actions/setup-python@v4`+, `docker/build-push-action@v4`+ — exact versions confirmed against each action's real latest major at Plan time, not guessed here).
- Evidence the gate works: a real PR with a deliberately failing test, screenshot of the red check and the blocked merge button, fixed in the same PR, screenshot of green — committed to `docs/evidence/`.

## Non-goals
- **No bonus items at all**, named explicitly so none is silently half-built under cover of "CI/CD polish": zero-downtime rolling-update-under-load demonstration (+4), GitOps via Argo CD/Flux (+4), deploy-by-digest with Cosign signing (+3), Prometheus + Grafana dashboard (+2, architecture already resolved in `docs/OPEN-DECISIONS.md` #11, execution not started and not started here), OpenTelemetry tracing frontend→backend→LLM (+2).
- This phase does **not** resolve `docs/OPEN-DECISIONS.md` #10 (which bonus items, if any, to pursue) — that decision is explicitly deferred past this phase; see the correction to #10 committed alongside this spec.
- No changes to `k8s/base/`'s object definitions — Phase 11/11b's manifests are consumed as-is. Only `k8s/overlays/prod/kustomization.yaml`'s image tag gets set, and only by CI (`kustomize edit set image`), never hand-written.
- No digest pinning (`@sha256:...` instead of a SHA tag) — that's the bonus upgrade path (ADR 0003, Alternatives), still gated behind #10.
- No new application code, and no new backend/frontend tests written here to hit the coverage/test-count numbers. If real measured backend coverage turns out to be below 65% during Verification, that gap is disclosed honestly and flagged back — writing more backend tests to close it is application-test-writing scope from earlier phases, not this phase's Non-goal-excluded CI/CD scope, and the gate is not silently lowered to make a number pass.
- No branch-protection rule configuration itself (GitHub Settings/API, not a repo file) — this phase makes the jobs exist and pass so they *can* be selected as required checks; actually selecting them is a manual step, and Category A's own separate rubric line, not Category I's.

## Open Questions

**1. Ephemeral cluster tool for `deploy-k8s`.** The assignment's own text says "kind/k3d," treating them as interchangeable. This project's local dev tooling is k3d (`docs/OPEN-DECISIONS.md` #4), but that decision was made for local iteration speed and an easier local-registry story — neither reason obviously carries over to a GitHub-hosted runner, which is thrown away after the job regardless. `kind` has a well-maintained first-party-adjacent GitHub Action (`helm/kind-action`) that's the more common choice for exactly this "ephemeral cluster inside a CI job" use case; using k3d in CI would mean installing it via its own install script inside the runner, a less-traveled path for this specific context.
**Recommendation:** use `kind` for `deploy-k8s` specifically (matching CI convention), while keeping k3d for local dev unchanged — these are two different tools for two different jobs, not a project-wide tooling change, and worth saying so explicitly rather than silently picking one.
**Not decided here — needs a call.**

**2. How the `integration` job reaches `/health`/`/ready` externally.** Confirmed directly by reading `frontend/nginx.conf`: it proxies only `location /api/` to `backend:8000`. `/health` and `/ready` are unprefixed root paths on the backend (`backend/app/routes/health.py`), not under `/api/` — a curl to `http://localhost:8080/ready` through the published frontend port would hit nginx's `location /` block and get the SPA's `index.html`, not the backend's real readiness response. Three ways to actually reach it, each with a real trade-off:
  (a) extend `nginx.conf` to also proxy `/health`/`/ready` — a real, if small, application-layer change, and arguably conflates the public-facing edge proxy with internal ops health-check plumbing;
  (b) publish a backend host port for the CI job specifically (a compose override file, or an inline `docker compose run` port publish) — not the same case as `docs/CLAUDE.md`'s automatic-deduction line (that's about a *database or cache* port in `compose.prod.yaml`; this is the backend API port, in dev `compose.yaml`, for CI only), but still a real deviation from the current "backend publishes nothing" shape;
  (c) reuse the project's own already-established pattern (Phase 6/11b) — an ephemeral helper container joined to the compose network via `docker network connect`, curling `backend:8000/ready` directly by service name, no host port needed at all.
**Not decided here — needs a call**, though (c) is the pattern already proven twice in this project and requires no new exposure.

**3. `kubeconform` and the VPA CustomResourceDefinition.** `kustomize build k8s/overlays/prod`'s output includes a `VerticalPodAutoscaler` object — a CRD kind kubeconform's default bundled OpenAPI schema set does not recognize out of the box. Untested here whether kubeconform's default behavior on an unrecognized CRD kind is a hard failure (breaking the `manifests` job on every run, on a resource that is in fact valid), a silent skip (defeating the point of the check for that resource), or requires an explicit flag/external schema location to handle correctly — this needs to actually be run once, not guessed.
**Not decided here — needs a real test run during Plan/implementation**, not an assumption either way.

**4. `integration` job teardown reliability.** `docker compose down -v` needs to run even if an earlier assertion step (the category check, the `X-Cache` check) fails — otherwise a failed run leaks containers/volumes on the runner. GitHub Actions' `if: always()` on the teardown step is the standard mechanism; confirming this is wired correctly (not just present) is a Plan/Verification detail rather than a design ambiguity, but is named here since it's a real, previously-seen-in-this-project failure mode (Phase 11b's own Job `backoffLimit` lesson: a resource-cleanup assumption that looked fine until something failed mid-run).

**5. Does `release.yml` re-run tests, or trust `cd.yml`'s?** The assignment's text for `release.yml` says only "on tag `v*` — build, push semver tags, generate release notes," with no test job named. Two readings: (a) a `v*` tag is only ever cut from a commit on `main` that already passed `cd.yml`'s `test` job, so `release.yml` trusts that and does not re-run the suite — leaner, but means a tag pushed against some other ref (a mistake, or a non-`main` commit) publishes an unverified release; (b) `release.yml` re-runs `test` itself, defensively, at the cost of duplicating `cd.yml`'s work on every release.
**Recommendation:** (a) — trust `cd.yml`, on the reasoning that this project's own branch model (`dev` for work, `main` protected, required checks) already makes "a tag on a commit that never passed CI" a process violation, not a case worth defending against with duplicated CI time; document that assumption directly in `release.yml`'s header comment so it's not silently implicit.
**Not decided here — needs a call.**

## Verification required
Run for real, exact commands, real output pasted in As-Built (not summarized):
1. A real PR against `main` triggers `ci.yml`; all seven jobs run and their real pass/fail status is captured (not just "the workflow file looks right").
2. `pytest --cov=app --cov-fail-under=65` run for real inside CI (or an equivalent local dry run first) — real coverage percentage reported, not assumed to already clear 65%.
3. The deliberately-failing-test PR: a real commit that fails one test, pushed, `ci.yml` goes red, merge button blocked — screenshot captured; then fixed in the same PR, `ci.yml` goes green — screenshot captured. Both committed to `docs/evidence/`.
4. A real merge to `main` triggers `cd.yml`; `build-push` real GHCR push confirmed (`ghcr.io/<owner>/<image>:<sha>` visible in the package registry, lowercase, real SBOM attached); `deploy-k8s` real ephemeral cluster stands up, `kubectl rollout status` succeeds, the Ingress smoke test passes, `kubectl get hpa` output captured.
5. `kubectl get deployment backend -n civicpulse -o jsonpath='{.spec.template.spec.containers[0].image}'` against the CI-deployed ephemeral cluster prints the real commit SHA tag — pasted directly into `git show <sha>` to confirm ADR 0003's "one-word answer" claim actually holds, not just in theory.
6. A real `v*` tag push triggers `release.yml`; real semver-tagged images visible in GHCR, real release notes generated.
7. `kustomize build k8s/overlays/prod | kubeconform` run for real at least once outside CI first, to resolve Open Question 3 before it can silently break the `manifests` job.

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md`, the assignment's §3.4 text, or is underspecified beyond what's captured in the Open Questions above, stop and ask — do not silently resolve. In particular: branch-protection rule configuration (which checks are marked "required," the ≥1-approval rule) is a manual GitHub Settings/API action this phase's committed files cannot themselves perform — Plan/implementation makes the jobs exist and pass reliably enough to *be* selected, and the actual selection is called out explicitly as a manual step in As-Built, not silently assumed done.

## Plan

## As-Built
