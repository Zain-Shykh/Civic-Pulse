# Phase 11b: Provider fail-fast + real HPA/VPA verification
Status: not started
Depends on: Phase 11 (`docs/specs/phase-11-kubernetes-manifests.md`) — reuses its manifests unchanged except where Deliverable (a) below requires an application-code change to `backend/app/providers/triage/factory.py`.
Reads first: `docs/OPEN-DECISIONS.md` #12 (the gap Deliverable (a) closes); `docs/specs/phase-11-kubernetes-manifests.md`'s As-Built, Verification item 13 (the VPA gap Deliverable (b) closes); the assignment's §3.3 "Horizontal scaling — HPA" and "Vertical scaling — VPA" sections verbatim (the HPA scale-out deliverable and the 5-step VPA loop: guess → load test → `kubectl describe vpa` → update requests → re-test); `backend/app/providers/triage/factory.py`; `backend/app/config.py`; `backend/app/main.py` (confirms `get_triage_provider()` runs inside FastAPI's `lifespan`, i.e. at process startup before any request is served); `backend/tests/test_triage_providers.py` (existing factory test pattern to extend, not replace); `k8s/base/vpa.yaml`, `hpa.yaml`, `backend.yaml`.

This is not a phase from `docs/IMPLEMENTATION-PLAN.md`'s original sequence — added after Phase 11 shipped, same pattern as Phase 9c after Phase 9. `docs/IMPLEMENTATION-PLAN.md` gets a matching entry in the same commit as this spec.

## Goal
Close the two gaps Phase 11 disclosed rather than fixed: (a) `backend` currently starts "healthy" with `TRIAGE_PROVIDER=llm` and an empty `GEMINI_API_KEY`, silently falling back to `rules:fallback` forever with no operator-visible signal; (b) `vpa.yaml`'s manifest is verified correct but has never actually produced a Target/Lower/Upper Bound recommendation, because the VPA controller components were never installed and no load test has ever been run against the cluster. This phase installs the controller components via a reviewed method, runs a real k6 load test, and closes the assignment's own 5-step VPA loop end to end.

## Deliverables

**(a) Application-level fail-fast in the triage factory.** `backend/app/providers/triage/factory.py`'s `_llm()` (confirmed at lines 30–34) constructs `LLMTriage(api_key=settings.gemini_api_key)` unconditionally — `settings.gemini_api_key` defaults to `""` (`backend/app/config.py:15`) and nothing currently checks it. `genai.Client` does not validate the key eagerly either (confirmed by Phase 10's own analysis: the failure only surfaces on the first real call, inside `LLMTriage`'s broad exception handling, as a silent `rules:fallback`). Add an explicit check in `_llm()`: if `settings.gemini_api_key` is empty/whitespace-only, raise immediately (before constructing `genai.Client` or `LLMTriage`) rather than letting a client get built that will silently fail every real call. Because `get_triage_provider()` runs inside `main.py`'s `lifespan` (confirmed `main.py:34`, executed before `uvicorn` starts serving), this raise happens at process startup — `uvicorn` fails to start, the container exits non-zero, and a Kubernetes Deployment shows this as `CrashLoopBackOff` in `kubectl get pods`, visibly and immediately, instead of a green "1/1 Running" hiding a dead provider. This also fails the Compose healthcheck for free (same container, same startup path), closing `docs/OPEN-DECISIONS.md` #12 at the one place both environments share.

**Test** (extends `backend/tests/test_triage_providers.py`'s existing `TestFactory` class, same style as its neighbors): construct the empty-key condition via `monkeypatch.setattr` on the `factory` module's `settings` object (the settings singleton is read once at import time; env-var monkeypatching alone would not reach it, matching how the existing tests already monkeypatch `os.environ["TRIAGE_PROVIDER"]` directly rather than through a settings object) with `TRIAGE_PROVIDER=llm`, and assert the raise happens without any network call attempted.

**(b) Real VPA controller install + HPA/VPA load-test loop.**

*Install method* — see Open Question 1 for the research behind this recommendation. Install the VPA controller components (recommender, updater, admission-controller) by applying, file-by-file, the individually-reviewed static YAML manifests from `kubernetes/autoscaler`'s `vertical-pod-autoscaler/deploy/` directory (RBAC + the three controller Deployments — the CRDs were already applied cleanly in Phase 11 via `vpa-v1-crd-gen.yaml` and don't need reapplying) via plain `kubectl apply -f`, never the aggregating `hack/vpa-up.sh` script. The admission-controller requires a TLS cert/key and a CA bundle registered on its `ValidatingWebhookConfiguration`; generate these via explicit, reviewed `openssl` commands (typed out and reviewed in this repo's Verification output, not executed as a downloaded `gencerts.sh`), replicating only the cryptographic operation that script performs, not its code.

*Load test.* `load/k6-script.js` (assignment's own repo layout, `§5.7` tree), targeting the Ingress's `POST /api/complaints` path with `TRIAGE_PROVIDER=rules` active on the target overlay (deterministic, no external network wait per request — maximizes achievable request rate for a given VU count, needed because the backend's per-request work is otherwise lightweight; see Open Question 2). Ramps virtual users over a sustained window long enough to cross the HPA's 60% CPU utilization target and to give the VPA recommender enough sampled history to produce a recommendation (VPA's recommender needs sustained history, not a single spike — exact ramp shape is Open Question 2, not decided here).

*The 5-step loop, run for real against a live k3d cluster, output captured in As-Built:*
1. Record the `resources.requests` already committed in `k8s/base/backend.yaml` (`500m` CPU / `256Mi` memory — Phase 11's guessed halved value, explicitly never treated as final).
2. Run the k6 load test; capture `kubectl get hpa -w` output showing replicas actually rising above the `minReplicas: 2` floor.
3. `kubectl describe vpa backend-vpa` — capture real, non-empty Target/Lower/Upper Bound recommendations.
4. Update `k8s/base/backend.yaml`'s `resources.requests` to match the VPA recommendation (a real manifest edit, committed).
5. Re-run the load test against the updated requests; report in As-Built what changed about HPA's behavior (scale-out threshold crossed earlier/later, different steady-state replica count, etc.) — the assignment's own "3–5 sentences on the lag between load arriving and capacity arriving" also gets written here, since it's this same load test that produces the evidence for it.

## Non-goals
- No CI/CD wiring — `cd.yml` is Phase 12's scope; nothing in `.github/workflows/` is touched here.
- No zero-downtime-under-load demonstration (`kubectl set image` during live load, zero failed requests) — still gated behind `docs/OPEN-DECISIONS.md` #10, unrelated to what this phase closes.
- No digest pinning, no GitOps — both still gated behind `docs/OPEN-DECISIONS.md` #10.
- No change to `k8s/base/hpa.yaml`'s tuned values (`minReplicas`/`maxReplicas`/60%/stabilization windows) — those are copied verbatim from the assignment per Phase 11 and stay as committed; only `backend.yaml`'s `resources.requests` changes, per the VPA loop's own step 4.
- No re-litigating Phase 11's Ingress/probe/Service/StatefulSet decisions — this phase only touches `backend.yaml`'s `resources.requests`, the new `load/k6-script.js`, the VPA controller-component install (cluster-level, not a `k8s/base` manifest — same category as `metrics-server`, per Phase 11's own Deliverable (k) note), and `backend/app/providers/triage/factory.py` + its test.

## Open Questions

**1. VPA controller-component install method.** Researched directly rather than assumed: the upstream `kubernetes/autoscaler` install docs (`vertical-pod-autoscaler/docs/installation.md`, fetched directly) document exactly one method — `git clone` the repo, then run `./hack/vpa-up.sh` inside it. There is no official versioned release artifact (tarball or manifest set) attached to a GitHub release, and no official Helm chart. Third-party Helm charts exist (`cowboysysop/vertical-pod-autoscaler`, `fairwinds-stable/vpa`, `stevehipwell/helm-charts`) but are unofficial packagings of the same upstream controller images by parties outside this project's control — installing one is not meaningfully safer from a supply-chain-review standpoint than running the official script, and it would introduce Helm as a new tool this project deliberately chose not to use (`docs/OPEN-DECISIONS.md` #3, Kustomize over Helm). Separately confirmed: Kubernetes' own "in-place pod resize" feature (stable as of 1.35) is a different, unrelated mechanism for resizing a running pod's resources without eviction — it does not include or replace the VPA controller components, which remain a separate install on every Kubernetes version checked.
**Recommendation:** apply the individual static YAML fragments (RBAC + the three controller Deployments) from the same already-reviewed repo checkout directly via `kubectl apply -f`, one file at a time, never the aggregating script — reviewing each file's content before applying it, the same posture already used successfully for the CRDs in Phase 11. Generate the admission-controller's required TLS material via explicit, reviewed `openssl` commands rather than running `gencerts.sh`.
**Decided:** _pending — awaiting explicit approval before this phase's Plan is written, given the added complexity relative to Phase 11's CRD-only install._

**2. k6 load profile — what actually crosses the HPA's 60% CPU threshold.** The backend's real endpoints do lightweight JSON validation, one DB write, and (with `TRIAGE_PROVIDER=rules`) a cheap regex/keyword pass — there is no CPU-heavy work in the app for k6 to amplify. Achieving even 60% of a `500m` CPU request (300m sustained) purely from HTTP load may require either a high sustained RPS or a specific target endpoint, and the exact VU/ramp/duration numbers that reliably produce this on a given host's CPU are not knowable in advance without running it.
**Recommendation:** target `POST /api/complaints` (the one endpoint that does real work per request: validation + triage + DB write) with `TRIAGE_PROVIDER=rules` on the load-test overlay (fastest provider — maximizes achievable request rate per VU, since no external network wait blocks each virtual user); start with a k6 ramp (e.g. stages ramping to some initial VU count over a few minutes) and treat the exact numbers as calibrated live against `kubectl top pods -n civicpulse`/`kubectl get hpa -w` output during the run, adjusting VU count upward if utilization doesn't move — not committed as a fixed profile blindly in advance. Exact numbers land in the Plan once Open Question 1 is resolved and real cluster capacity (host CPU cores available to k3d) is confirmed.
**Decided:** _pending._

## Verification required
Run against a real k3d cluster, exact commands, real output pasted in As-Built (not summarized):
1. `pytest backend/tests/test_triage_providers.py -k fail_fast` (or equivalent) — new test passes; full `pytest` suite still green.
2. `k3d cluster create` (or reuse), rebuild/import `civicpulse-backend:dev` with the factory change, `kubectl apply -k k8s/overlays/dev`.
3. Manually set `TRIAGE_PROVIDER=llm` with an empty/placeholder `GEMINI_API_KEY` on a scratch Deployment (or patch the existing one) and confirm via `kubectl get pods -n civicpulse` that it shows `CrashLoopBackOff`, then revert.
4. Apply the VPA controller-component manifests (Open Question 1's decided method) and confirm `kubectl get pods -n kube-system` (or wherever they land) shows recommender/updater/admission-controller `Running`.
5. `kubectl top pods -n civicpulse` baseline before load.
6. Run `k6 run load/k6-script.js` against the Ingress; `kubectl get hpa -n civicpulse -w` output captured showing replicas rising above 2.
7. `kubectl describe vpa backend-vpa -n civicpulse` — real Target/Lower/Upper Bound recommendation captured.
8. Update `k8s/base/backend.yaml`'s `resources.requests` to the recommendation; `kubectl apply -k k8s/overlays/dev` again.
9. Re-run `k6 run load/k6-script.js`; capture `kubectl get hpa -w` again; write the 3–5 sentence comparison (assignment's own required text) into As-Built.
10. A replicas-vs-load chart (from k6's own summary output or `kubectl get hpa -w` timestamps) committed alongside As-Built.
11. Teardown: `kubectl delete -k k8s/overlays/dev`, remove the VPA controller-component objects, `k3d cluster delete` (or confirm intended to keep the cluster for a later phase).

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md`, the assignment's §3.3 text, or is underspecified beyond what's captured in the Open Questions above, stop and ask — do not silently resolve.

## Plan


## As-Built
