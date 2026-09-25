# Phase 11b: Provider fail-fast + real HPA/VPA verification
Status: in progress — Plan drafted, awaiting approval before implementation
Depends on: Phase 11 (`docs/specs/phase-11-kubernetes-manifests.md`) — reuses its manifests unchanged except where Deliverable (a) below requires an application-code change to `backend/app/providers/triage/factory.py`.
Reads first: `docs/OPEN-DECISIONS.md` #12 (the gap Deliverable (a) closes); `docs/specs/phase-11-kubernetes-manifests.md`'s As-Built, Verification item 13 (the VPA gap Deliverable (b) closes); the assignment's §3.3 "Horizontal scaling — HPA" and "Vertical scaling — VPA" sections verbatim (the HPA scale-out deliverable and the 5-step VPA loop: guess → load test → `kubectl describe vpa` → update requests → re-test); `backend/app/providers/triage/factory.py`; `backend/app/config.py`; `backend/app/main.py` (confirms `get_triage_provider()` runs inside FastAPI's `lifespan`, i.e. at process startup before any request is served); `backend/tests/test_triage_providers.py` (existing factory test pattern to extend, not replace); `k8s/base/vpa.yaml`, `hpa.yaml`, `backend.yaml`.

This is not a phase from `docs/IMPLEMENTATION-PLAN.md`'s original sequence — added after Phase 11 shipped, same pattern as Phase 9c after Phase 9. `docs/IMPLEMENTATION-PLAN.md` gets a matching entry in the same commit as this spec.

## Goal
Close the two gaps Phase 11 disclosed rather than fixed: (a) `backend` currently starts "healthy" with `TRIAGE_PROVIDER=llm` and an empty `GEMINI_API_KEY`, silently falling back to `rules:fallback` forever with no operator-visible signal; (b) `vpa.yaml`'s manifest is verified correct but has never actually produced a Target/Lower/Upper Bound recommendation, because the VPA controller components were never installed and no load test has ever been run against the cluster. This phase installs the controller components via a reviewed method, runs a real k6 load test, and closes the assignment's own 5-step VPA loop end to end.

## Deliverables

**(a) Application-level fail-fast in the triage factory.** `backend/app/providers/triage/factory.py`'s `_llm()` (confirmed at lines 30–34) constructs `LLMTriage(api_key=settings.gemini_api_key)` unconditionally — `settings.gemini_api_key` defaults to `""` (`backend/app/config.py:15`) and nothing currently checks it. `genai.Client` does not validate the key eagerly either (confirmed by Phase 10's own analysis: the failure only surfaces on the first real call, inside `LLMTriage`'s broad exception handling, as a silent `rules:fallback`). Add an explicit check in `_llm()`: if `settings.gemini_api_key` is empty/whitespace-only, raise immediately (before constructing `genai.Client` or `LLMTriage`) rather than letting a client get built that will silently fail every real call. Because `get_triage_provider()` runs inside `main.py`'s `lifespan` (confirmed `main.py:34`, executed before `uvicorn` starts serving), this raise happens at process startup — `uvicorn` fails to start, the container exits non-zero, and a Kubernetes Deployment shows this as `CrashLoopBackOff` in `kubectl get pods`, visibly and immediately, instead of a green "1/1 Running" hiding a dead provider. This also fails the Compose healthcheck for free (same container, same startup path), closing `docs/OPEN-DECISIONS.md` #12 at the one place both environments share.

**Test** (extends `backend/tests/test_triage_providers.py`'s existing `TestFactory` class, same style as its neighbors): construct the empty-key condition via `monkeypatch.setattr` on the `factory` module's `settings` object (the settings singleton is read once at import time; env-var monkeypatching alone would not reach it, matching how the existing tests already monkeypatch `os.environ["TRIAGE_PROVIDER"]` directly rather than through a settings object) with `TRIAGE_PROVIDER=llm`, and assert the raise happens without any network call attempted.

**(b) Real VPA controller install + HPA/VPA load-test loop.**

*Install method* — see Open Question 1 for the research behind this recommendation. Install by applying, file-by-file, the individually-reviewed static YAML manifests from `kubernetes/autoscaler`'s `vertical-pod-autoscaler/deploy/` directory via plain `kubectl apply -f`, never the aggregating `hack/vpa-up.sh` script (the CRDs, `vpa-v1-crd-gen.yaml`, were already applied cleanly this way in Phase 11 — this phase reapplies them fresh, since Phase 11's cluster was torn down).

**Scope narrowed during Plan-drafting, stated here rather than left only in the Plan:** confirmed directly against `kubernetes/autoscaler`'s own `docs/components.md` — the **recommender** alone computes and writes the Target/Lower/Upper Bound recommendation onto the VPA object's `.status` (what `kubectl describe vpa` shows). The **updater** (evicts pods to apply a recommendation) and **admission-controller** (mutates pod specs at creation time via a webhook) both only matter in `Auto`/`Initial` update modes — this project's VPA is deliberately `updateMode: "Off"` (Phase 11, Deliverable (k)), so neither ever does anything here. Installing them would mean standing up an entire TLS-secured admission webhook (a real cert-generation/registration exercise, and correspondingly a real source of first-attempt failure — Open Question 1) purely to run code that structurally cannot fire under this project's own chosen mode. **Deliverable (b) therefore installs only `vpa-rbac.yaml` (the full file, applied as one reviewed unit — it also defines unused ServiceAccounts/ClusterRoles for the other two components, which is harmless) and `recommender-deployment.yaml`.** `updater-deployment.yaml`, `admission-controller-deployment.yaml`, and `admission-controller-service.yaml` are not applied, and no TLS material is generated at all.

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
**Decided:** accepted as recommended, narrowed further during Plan-drafting (see the scope note under Deliverable (b) above): only `vpa-rbac.yaml` + `recommender-deployment.yaml` are applied, since `docs/components.md` confirms only the recommender writes the recommendation and this project's VPA is `Off` mode — no TLS cert generation, no admission-controller, no updater. Full sequencing in the Plan below.

**2. k6 load profile — what actually crosses the HPA's 60% CPU threshold.** The backend's real endpoints do lightweight JSON validation, one DB write, and (with `TRIAGE_PROVIDER=rules`) a cheap regex/keyword pass — there is no CPU-heavy work in the app for k6 to amplify. Achieving even 60% of a `500m` CPU request (300m sustained) purely from HTTP load may require either a high sustained RPS or a specific target endpoint, and the exact VU/ramp/duration numbers that reliably produce this on a given host's CPU are not knowable in advance without running it.
**Recommendation:** target `POST /api/complaints` (the one endpoint that does real work per request: validation + triage + DB write) with `TRIAGE_PROVIDER=rules` on the load-test overlay (fastest provider — maximizes achievable request rate per VU, since no external network wait blocks each virtual user); start with a k6 ramp (e.g. stages ramping to some initial VU count over a few minutes) and treat the exact numbers as calibrated live against `kubectl top pods -n civicpulse`/`kubectl get hpa -w` output during the run, adjusting VU count upward if utilization doesn't move — not committed as a fixed profile blindly in advance. Exact numbers land in the Plan once Open Question 1 is resolved and real cluster capacity (host CPU cores available to k3d) is confirmed.
**Decided:** accepted as recommended. Starting VU/ramp guess and target-endpoint reasoning are in the Plan below; final numbers are calibrated live during Verification, not fixed here.

## Verification required
Run against a real k3d cluster, exact commands, real output pasted in As-Built (not summarized):
1. `pytest backend/tests/test_triage_providers.py -k fail_fast` (or equivalent) — new test passes; full `pytest` suite still green.
2. `k3d cluster create` (or reuse), rebuild/import `civicpulse-backend:dev` with the factory change, `kubectl apply -k k8s/overlays/dev`.
3. Manually set `TRIAGE_PROVIDER=llm` with an empty/placeholder `GEMINI_API_KEY` on a scratch Deployment (or patch the existing one) and confirm via `kubectl get pods -n civicpulse` that it shows `CrashLoopBackOff`, then revert.
4. Apply the CRDs, then `vpa-rbac.yaml`, then `recommender-deployment.yaml` only (Open Question 1's decided, narrowed method) and confirm `kubectl get pods -n kube-system -l app=vpa-recommender` shows `Running`.
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

No code changes exist yet — `backend/app/providers/triage/factory.py`, `backend/tests/test_triage_providers.py`, `k8s/base/backend.yaml`, `k8s/base/vpa.yaml`, `k8s/base/hpa.yaml` re-read directly at Plan-drafting time, unchanged since Phase 11 and since the spec draft above. `load/k6-script.js` does not exist yet — confirmed no `load/` directory exists in the repo currently.

### (a) Application-level fail-fast

**`backend/app/providers/triage/factory.py`** — `_llm()` currently (lines 30–34):
```python
def _llm() -> TriageProvider:
    from app.providers.triage.llm import LLMTriage

    return LLMTriage(api_key=settings.gemini_api_key)
```
Change to add the check as the first statement inside the function, before `LLMTriage(...)` is ever constructed:
```python
def _llm() -> TriageProvider:
    from app.providers.triage.llm import LLMTriage

    if not settings.gemini_api_key.strip():
        raise RuntimeError(
            "TRIAGE_PROVIDER=llm requires a non-empty GEMINI_API_KEY; "
            "refusing to start rather than silently falling back to rules on every call."
        )
    return LLMTriage(api_key=settings.gemini_api_key)
```
`RuntimeError`, not a new custom exception class — matches this same file's existing fail-fast (`get_triage_provider()`'s bare `KeyError` on an unrecognized/unimplemented provider, already accepted by ADR 0001 as satisfying "fail fast at startup"); no new abstraction earns its keep for one call site. No change to `get_triage_provider()` itself, no change to `app/config.py` (its `gemini_api_key: str = ""` default is exactly what the check reads), no change to `main.py` (the raise propagates up through the existing `lifespan` unchanged — confirmed that's enough to fail `uvicorn`'s startup, no new handling needed there).

**`backend/tests/test_triage_providers.py`** — add one method to the existing `TestFactory` class, after `test_factory_fails_fast_on_not_yet_implemented_ollama`:
```python
def test_factory_fails_fast_on_llm_provider_with_empty_api_key(self, monkeypatch):
    monkeypatch.setenv("TRIAGE_PROVIDER", "llm")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(RuntimeError):
        get_triage_provider()
```
Requires one new import at the top of the file: `from app.config import settings`. `settings` is a mutable Pydantic v2 `BaseSettings` instance (`app/config.py`'s `model_config` sets `env_file`/`extra` only, no `frozen` — confirmed directly, so `monkeypatch.setattr` on its field works and auto-reverts after the test like any other monkeypatch). No mock of `genai.Client`/`LLMTriage` needed: the raise happens before either is constructed, so "no network call attempted" is structurally guaranteed by the code's own ordering, not something the test has to separately assert.

### (b) VPA recommender install + load-test loop

**Cluster prerequisites, in order:**
1. `k3d cluster create civicpulse` (Phase 11's cluster was torn down in its own Verification step 15 — this is a fresh cluster, not a reused one).
2. Rebuild `civicpulse-backend:dev` (source changed by (a) above) and `civicpulse-frontend:dev` (rebuild for symmetry, same as Phase 11), `k3d image import` both.
3. `kubectl apply -k k8s/overlays/dev` — brings up the full Phase 11 stack unchanged (namespace, ConfigMap/Secret, Postgres/Redis, backend/frontend, Ingress, HPA, VPA object, PDB). `vpa.yaml`'s `backend-vpa` object applies immediately, same as Phase 11 — it just has nothing consuming it yet until the recommender exists.
4. Re-apply the VPA CRDs (`vpa-v1-crd-gen.yaml`, same file already reviewed in Phase 11) — needed fresh on this new cluster.

**Ingress reachability for k6 — a deliberate change from Phase 11's verification approach:** Phase 11 used `kubectl port-forward -n kube-system svc/traefik 18080:80` for one-off `curl` checks, which is fine for a handful of sequential requests but is a single tunneled connection — a real risk under k6's concurrent virtual users (port-forward is not designed for sustained multi-connection throughput and could bottleneck load artificially, making HPA/VPA see load-generator-side contention instead of real backend CPU pressure). This phase instead creates the cluster with a published load-balancer port (`k3d cluster create civicpulse -p "8080:80@loadbalancer"`) so k6 hits `http://127.0.0.1:8080` directly (with a `Host: civicpulse.local` header) with no `kubectl` process in the request path. **Named risk, with fallback:** if binding host port 8080 fails (port already in use, or some other host constraint), fall back to port-forward but disclose in As-Built that achieved RPS may be artificially capped by the tunnel rather than by backend/cluster capacity — do not present a port-forward-bottlenecked run as a clean capacity signal.

**RBAC + recommender, in order:**
5. Apply `vpa-rbac.yaml` (full file, one reviewed unit — see Deliverable (b)'s scope note: it also defines unused `updater`/`admission-controller` ServiceAccounts/ClusterRoles, left harmlessly unused).
6. Apply `recommender-deployment.yaml` only. Confirm `kubectl get pods -n kube-system -l app=vpa-recommender` shows `Running`.
7. `kubectl describe vpa backend-vpa -n civicpulse` at idle, before any load — the recommender samples continuously once running, so an early/rough recommendation may already be forming; captured as a labeled "idle baseline," not the post-load result.

**`load/k6-script.js`** — new file. Shape (not final numbers, per Open Question 2's decision):
- `POST` to `/api/complaints` (via `Host: civicpulse.local`) with a `{ text, location }` JSON body drawn from a small in-script pool of realistic complaint strings (avoids k6 hammering the exact same string every request, which is closer to real traffic and avoids any accidental dedup/caching path).
- `TRIAGE_PROVIDER=rules` confirmed active on `k8s/overlays/dev` (base default, unchanged — no overlay patch needed).
- `checks`: response status is `201`.
- `options.stages`: a starting guess only — ramp up over ~1 minute, hold for several minutes (long enough to give the recommender real sampled history, not just a spike), ramp down. Exact VU counts and durations are read live against `kubectl top pods -n civicpulse` / `kubectl get hpa -n civicpulse -w` during the actual run in Verification and adjusted upward if CPU utilization isn't moving — the script committed in As-Built reflects whatever numbers actually produced a real scale-out, not the first guess blindly.

**Named risk, with fallback (recommender history window):** VPA's recommender needs some sustained history before its estimator stabilizes, not a single short burst — a too-short load window may produce a technically non-empty but wide/early-stage recommendation. If the first `kubectl describe vpa` capture after a load run looks unstable or unchanged from the idle baseline, the load window is extended (longer hold stage) and the cluster is left running a bit longer before re-describing, rather than accepting the first capture uncritically.

**Named risk, with fallback (host capacity):** the host this runs on is a shared machine already noted in Phase 11 As-Built as being under real disk pressure; there is no equivalent prior confirmation of spare CPU headroom for k3d's node. If, after reasonable calibration (a few VU-count increases, confirmed via `kubectl top pods` actually rising), HPA still will not cross 60% or the VPA recommendation still looks degenerate, this gets disclosed honestly in As-Built exactly like Phase 11 disclosed its disk-pressure friction and its VPA-controller gap — not silently extrapolated or asserted as passing.

**5-step loop execution order (matches the spec's Deliverable (b) list and Verification required list exactly):**
1. Record `k8s/base/backend.yaml`'s current `resources.requests` (`500m`/`256Mi` — Phase 11's guess).
2. Run `k6 run load/k6-script.js`, `kubectl get hpa -n civicpulse -w` captured live in parallel.
3. `kubectl describe vpa backend-vpa -n civicpulse` — capture the real Target/Lower/Upper Bound.
4. Edit `k8s/base/backend.yaml`'s `resources.requests` (cpu and memory) to match the captured recommendation; `kubectl apply -k k8s/overlays/dev` to roll it out.
5. Re-run the identical k6 script; capture `kubectl get hpa -w` again; compare against run 1 in As-Built, and write the assignment's required 3–5 sentences on load-arrival-vs-capacity-arrival lag using this run's own timestamps as evidence, not a generic restatement.

**Teardown:** delete the recommender Deployment + `vpa-rbac.yaml` objects, `kubectl delete -k k8s/overlays/dev`, `k3d cluster delete`.

**Uncertain, flagged rather than guessed:** the exact k6 VU/stage numbers, and whether the published-port k3d flag works cleanly on first try given this host's prior resource friction (Phase 11's disk-pressure history) — both are calibrated live in Verification, and either genuinely not working after reasonable effort is disclosed in As-Built rather than forced.

## As-Built
