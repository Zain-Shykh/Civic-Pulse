# Engineering notes — the eight questions (assignment §5.2)

Every answer below cites a real file and line in this repository, checked by re-opening the cited line before writing it down — not a generic answer.

## 1. Three things that differ between your laptop and a CI runner, and the exact line that freezes each

1. **Python interpreter version.** A developer's laptop can have any Python on `PATH`. `backend/Dockerfile:3` (`FROM python:3.12-slim AS builder`) and `:16` (`FROM python:3.12-slim AS runtime`) freeze the exact interpreter for every build and every CI job that runs the backend in a container (`ci.yml`'s `test-backend` job pins the same version again independently via `container: image: python:3.12-slim`, `ci.yml:44-45`).
2. **Node interpreter version.** `frontend/Dockerfile:3` (`FROM node:22-alpine AS builder`) freezes the exact Node major used to build the frontend, regardless of whatever `node --version` a laptop happens to have installed globally.
3. **PostgreSQL and Redis server versions.** `compose.yaml:68` (`image: postgres:16-alpine`) and `compose.yaml:90` (`image: redis:7-alpine`) freeze the exact server versions every environment runs against — a laptop with a natively-installed Postgres/Redis (not via this Compose file) could otherwise silently run a different major version than CI's services (`ci.yml:48`, `:59`, the same two tags).

## 2. Where your pipeline sits on the CI/CD maturity ladder

**Honest gap, not filled in with a guess:** I don't have access to "Lecture 03, slide 32" — its specific rung names/taxonomy aren't in any file in this repository, and inventing a plausible-sounding one to match a slide I haven't seen would be exactly the kind of unverified claim `docs/WORKFLOW.md` rules out. Fill in the rung name your own lecture deck uses; the real, cited pipeline behavior below is what should justify whichever rung name you pick.

What's real and automated today: every PR triggers `ci.yml` (lint, type-check, backend+frontend tests, image build, Trivy scan, kubeconform manifest validation, a full Compose integration smoke test — all 7 jobs, `.github/workflows/ci.yml`); every merge to `main` triggers `cd.yml`, which re-runs the test suite on the merged commit, builds and pushes both images to GHCR tagged by commit SHA, then deploys to a fresh ephemeral `kind` cluster and waits on rollout status plus a real Ingress smoke test (`.github/workflows/cd.yml`); tagging a release re-tags the already-built, already-tested SHA image rather than rebuilding (`.github/workflows/release.yml`, its own header comment). What's *not* automated: no progressive/canary rollout, no automated rollback on a failed post-deploy health check (rollback is a manual `kubectl rollout undo` or manual redeploy, per `docs/adr/0003-deploy-by-sha.md`'s Consequences), and no GitOps reconciliation loop watching the cluster against the repo (Argo CD/Flux is explicitly unbuilt bonus scope, `docs/RUBRIC-CHECKLIST.md`'s Bonus table). That's the real evidence — match it to your lecture's actual rung names.

## 3. The exact line guaranteeing build-once-deploy-many, and what breaks without it

`cd.yml`'s `build-push` job tags both images with the one real commit SHA and nothing else propagates a different identity downstream:

```
ghcr.io/${{ steps.lc.outputs.owner }}/civicpulse-backend:${{ github.sha }}   # cd.yml:95
ghcr.io/${{ steps.lc.outputs.owner }}/civicpulse-frontend:${{ github.sha }}  # cd.yml:107
```

`deploy-k8s` (`cd.yml:170-175`) injects that exact same tag via `kustomize edit set image civicpulse-backend=...:${{ github.sha }} civicpulse-frontend=...:${{ github.sha }}` — the same bytes built once in `build-push` are the same bytes deployed, never rebuilt from source a second time for deployment. `docs/adr/0003-deploy-by-sha.md` is the full decision record.

**What breaks without it:** without a single SHA flowing through the whole pipeline, a rebuild-per-stage setup can produce different bytes at each stage (a base-image security patch landing between builds, non-pinned transitive dependency resolution, a flaky build step) — "works in CI" and "what's actually running in prod" stop being provably the same artifact, and `docs/adr/0003-deploy-by-sha.md`'s "what is production running?" one-command answer (`kubectl get deployment ... -o jsonpath='{.spec.template.spec.containers[0].image}'`) would no longer correspond to anything a `git show <sha>` could reproduce.

## 4. With a live LLM provider, your service is probabilistic. What does "correct" mean, and how did you keep CI deterministic?

CI never calls a live LLM at all — `TRIAGE_PROVIDER: simulated` (`ci.yml:66`, and `cd.yml`'s equivalent `test-backend` job) selects `SimulatedTriage` (`backend/app/providers/triage/simulated.py:49-59`), which cycles through six fixed fixtures (`simulated.py:15-46`) with no randomness and no network call — every test run sees the exact same sequence, by construction.

For the real `LLMTriage` path (never exercised in CI), "correct" cannot mean "matches one ground-truth label" — there is no labeled dataset, and the model's actual category choice is genuinely probabilistic. What's actually tested and asserted instead (`backend/tests/test_llm_triage.py`) are the invariants that must hold regardless of what Gemini returns: the response always validates against `_LLMResponseSchema` or falls back safely (`llm.py:97`, `TestMalformedResponse`), a prompt-injection attempt still yields a schema-valid category rather than an arbitrary string (`TestPromptInjectionGuardrail`), and retryable vs. non-retryable failures are handled per the allow-list (`llm.py:52-58`, `TestRetryableFailures`/`TestNonRetryableFailure`). `RuleBasedTriage`'s own keyword table was checked once for rough fixture-consistency against `seed.py`'s synthetic labels — but that file's own docstring (`rules.py:1-8`) explicitly disclaims this as *not* an accuracy measurement. "Correct" here means schema-safe and fallback-safe under any model output, not classification accuracy — see `docs/TRIAGE.md`.

## 5. Your HPA lag: how many seconds between offered load rising and replicas rising? Where did the time go, and what would reduce it?

This data already exists and is real, captured in `docs/specs/phase-11b-failfast-and-vpa-verification.md`'s As-Built — cited directly, not re-derived:

> Real utilization became visible ~80s after a fresh rollout (metrics-server's own warm-up, not an HPA property), but once metrics were flowing, HPA reacted to a 79–89%-utilization breach within one 20s poll interval and scaled `2 → 3` — consistent with the tuned `scaleUp.stabilizationWindowSeconds: 0` giving essentially zero deliberate scale-up delay. The mirror-image lag is on the way down: utilization dropped to near-zero within ~15s of the load Job completing, but HPA held the extra replica for the full ~285s `scaleDown.stabilizationWindowSeconds: 300` window before releasing it. (`docs/specs/phase-11b-failfast-and-vpa-verification.md:305`)

Concretely: `2 → 3` at `t=100s` (`docs/specs/phase-11b-failfast-and-vpa-verification.md:269`), scale-down completing at `14:44:42` against the load Job finishing at `14:39:57` — `285s`, matching the tuned `300s` window (`:291`, `:299`, `:303`). Where the time actually went: ~80s of it is metrics-server's warm-up after a fresh rollout, not HPA reaction time; the true HPA reaction to a real utilization breach is near-immediate (`stabilizationWindowSeconds: 0` on scale-up). What would reduce it: nothing on the scale-up side without accepting flappier behavior (it's already tuned to ~zero deliberate delay); the metrics-server warm-up gap is a cluster-bootstrap cost, not something this project's own manifests control.

## 6. Why VPA is in Off mode. Describe the failure mode of running it in Auto alongside your HPA

Quoted directly from `docs/specs/phase-11-kubernetes-manifests.md:42`, not restated from memory:

> HPA scales replica count on CPU utilization; if VPA also ran in `Auto` mode adjusting the backend's CPU *request*, the two would fight over the same signal — VPA raising the request lowers computed utilization (usage ÷ request), which makes HPA scale in, which raises per-pod load, which makes VPA raise the request again, an oscillating loop with no stable point. Recommender-only mode breaks the loop: VPA only *suggests* ... a human reviews and manually updates `resources.requests` in the manifest, and HPA continues scaling on whatever request value is currently committed.

`k8s/base/vpa.yaml`'s `updatePolicy.updateMode: "Off"` is the manifest-level enforcement of this decision.

## 7. Your `internal: true` network blocks outbound traffic. Where does that leave the service that calls a hosted LLM, and how did you resolve it?

`compose.yaml:4-9` defines two networks: `edge` (plain bridge, frontend↔backend) and `internal` (`internal: true`, backend↔postgres↔redis — genuinely no route to the outside world). `backend` is the only service on both (`compose.yaml:41-44`, `# The only service that bridges edge and internal`). Docker's `internal: true` flag blocks *that specific network* from any external routing — it does not touch `edge`, which is a normal bridge network with the default outbound NAT any non-internal Docker network gets. So `backend`'s outbound HTTPS call to Gemini goes out over its `edge` membership's ordinary egress path, while `postgres`/`redis` (members of `internal` only) have no route out at all, and `frontend` (a member of `edge` only) has no route to the database tier. No special resolution was needed beyond this network topology itself — the isolation this question worries about (frontend reaching the database) is what `internal: true` is actually for; it was never meant to, and doesn't, block the one service that legitimately needs external egress. `docs/adr/0004-pii-and-data-governance.md` covers the separate, real concern of *what* crosses that egress path (redaction before it leaves).

## 8. The failure. Something cost you more than an hour

The Traefik `helm install --wait` timeout during `cd.yml`'s `deploy-k8s` job (Phase 12, PRs #10–#12) — quoted directly from `docs/specs/phase-12-ci-cd.md`, not re-narrated from memory:

> **Symptom:** `helm install traefik ... --wait --timeout 120s` → "context deadline exceeded." (`phase-12-ci-cd.md:195`)
> **What was wrongly believed first:** that the Traefik pod itself wasn't becoming Ready in time, and/or that `--set service.type=ClusterIP` (the first fix attempt, PR #11) had corrected the actual problem — it hadn't; Helm silently ignored that value path rather than erroring (`phase-12-ci-cd.md:196`).
> **The exact thing that finally told the truth:** a `Diagnose Traefik install` step added specifically to see why (`if: failure()`), which showed the pod was `Ready` in ~3 seconds both times — the real blocker was the chart's default `Service: LoadBalancer`, whose `EXTERNAL-IP` never leaves `<pending>` on `kind` (no cloud LB controller), and `helm --wait` waits on that Service too, not just the pod. Confirming the *correct* value path required installing Helm locally and running `helm template traefik/traefik --set service.spec.type=ClusterIP` against the chart's real `values.yaml` before pushing the fix (`phase-12-ci-cd.md:197`, `:207`) — the path is `service.spec.type`, not the more obvious-looking `service.type`.

Real total cost: three separate PRs (#10 added the diagnostic, #11 was the first wrong fix, #12 was the real fix) before `cd.yml`'s `deploy-k8s` job went green — well over an hour once diagnosis, the wrong fix's own CI round-trip, and the correct fix's local verification are counted together.
