# Phase 11: Kubernetes manifests
Status: in progress
Depends on: Phase 10 (compose hardening — this phase deploys the same two images, backend/frontend, that Phase 10 just hardened; postgres/redis are the same stock pinned images compose already uses, not something Phase 10 touched)
Reads first: assignment §3.3 (Kubernetes, verbatim code blocks); `docs/IMPLEMENTATION-PLAN.md` Phase 11 entry; `docs/CONTRACTS.md` (API surface, schema); `docs/adr/0001-provider-interface.md`; `docs/adr/0003-deploy-by-sha.md`; `docs/OPEN-DECISIONS.md` #4, #10; `docs/PARALLEL-WORK-PLAN.md`; `k8s/base/README.md`, `k8s/overlays/dev/README.md`, `k8s/overlays/prod/README.md`; `compose.prod.yaml`; `compose.yaml`; `backend/app/config.py`; `backend/app/routes/health.py`; `backend/Dockerfile`; `frontend/Dockerfile`

## Goal
From-scratch Kustomize manifests (`k8s/base` + `overlays/dev` + `overlays/prod`) that run the whole CivicPulse stack — backend, frontend, Postgres, Redis — on a local k3d cluster, translating the env-var/secret shape Phase 10 just hardened in `compose.prod.yaml` into Kubernetes-native ConfigMap/Secret objects, with correctly-differentiated probes, autoscaling (HPA + VPA), and a disruption budget, exactly as scoped by the assignment's §3.3 object table and the code blocks that follow it.

## Deliverables

**Confirmed directly before writing this list:** `k8s/base/README.md`, `k8s/overlays/dev/README.md`, `k8s/overlays/prod/README.md` currently contain one placeholder line each (the base README already names the intended object list: "namespace, backend, frontend, postgres, redis, ingress, configmap, secret, hpa, vpa, pdb" — matches this phase's scope, nothing already decided there gets overwritten, only expanded into real manifests). `compose.prod.yaml` and `backend/app/config.py` read directly to confirm the exact env vars/connection-string shapes below.

**(a) Namespace** — `civicpulse` (assignment table verbatim: "Everything in civicpulse, never default"; also already assumed by ADR 0003's own `kubectl` examples, e.g. `-n civicpulse`).

**(b) ConfigMap** (`civicpulse-config`) — non-secret only:
- `REDIS_URL=redis://redis:6379/0` (redis has no auth in compose today — confirmed, no `REDIS_PASSWORD` anywhere in `.env.example` or either compose file — so this is genuinely non-secret)
- `TRIAGE_PROVIDER` — base default `rules` (no key needed, matches `compose.yaml`'s own dev default), overridden per-overlay (see (m))
- `POSTGRES_USER`, `POSTGRES_DB` — identifiers, not secrets; consumed by both the backend container (as part of building its view of the world) and the postgres StatefulSet

**(c) Secret** (`civicpulse-secret`) — committed manifest carries **placeholder values only** (rubric H, "committed manifests carry placeholders only"), real values injected separately, never committed:
- `POSTGRES_PASSWORD`
- `GEMINI_API_KEY`
- `DATABASE_URL` — the **full composed connection string**, not split across ConfigMap/Secret. Confirmed via `backend/app/config.py:13`, the app reads one `DATABASE_URL` env var (`postgresql+psycopg://user:pass@postgres:5432/db`); Kubernetes has no native mechanism to string-interpolate a `valueFrom` ConfigMap key and a `valueFrom` Secret key into one env var without an entrypoint wrapper script the image doesn't have (confirmed via `backend/Dockerfile:35`, `CMD` is a bare `uvicorn` invocation, no wrapper). Since the string contains `POSTGRES_PASSWORD`, the whole string must live in the Secret, even though most of its content (`postgres:5432`, `${POSTGRES_DB}`) is not itself sensitive. This is a K8s mechanical constraint, not a judgment call.

**(d) Deployment: backend**, ≥2 replicas (assignment floor). Container port `8000` (matches `backend/Dockerfile:30`, `EXPOSE 8000`). `resources.requests`/`.limits` on the container (exact numbers — Open Question 3). Three probes, differentiated per assignment's own code block and confirmed against `backend/app/routes/health.py`:
  - `startupProbe`: `GET /health`, `failureThreshold: 30`, `periodSeconds: 2` — tolerates slow boot, doesn't gate on the DB.
  - `livenessProbe`: `GET /health` — confirmed via `health.py:19-22`, the handler does not call `db_ping`/`redis_ping` at all, just returns `{"status": "ok"}"` — genuinely independent of Postgres/Redis, satisfying "must NOT depend on the database."
  - `readinessProbe`: `GET /ready` — confirmed via `health.py:25-38`, calls both `db_ping()` and `redis_ping()` and returns 503 naming the failed dependency if either is down — genuinely dependent, satisfying "SHOULD depend on the database."

**(e) Deployment: frontend**, ≥2 replicas. Container port `8080` (matches `frontend/Dockerfile:33`). A single `httpGet: { path: /, port: 8080 }` probe reused for both liveness and readiness (no startup probe needed either — a static nginx server serving pre-built files has no slow-boot risk and no dependency to distinguish liveness from readiness the way the backend has). This matches the frontend image's own `HEALTHCHECK` (`frontend/Dockerfile:36`, `wget --spider http://127.0.0.1:8080/`) — reusing the same path the image author already chose, not inventing a new one.

**(f) StatefulSet: postgres**, 1 replica, image `postgres:16-alpine` (same pinned tag `compose.prod.yaml:57` already uses — reused unchanged, not one of "the images Phase 10 hardened," since postgres/redis are stock upstream images, only backend/frontend are the custom-built ones). `volumeClaimTemplates` → PVC for `/var/lib/postgresql/data` (assignment: "A Deployment for a database is a marked error" — StatefulSet + PVC required so pod identity and storage survive rescheduling; the PVC binds to the same underlying volume regardless of which node/pod attaches to it, which a bare Deployment + PVC cannot guarantee under multi-replica rescheduling — moot here at replica 1, but StatefulSet is still what the assignment requires and is ready to justify at viva: ordered, stable network identity plus one PVC per ordinal, versus a Deployment's interchangeable, identity-less pods sharing whatever PVC binding happens to exist). `resources.requests`/`.limits` (Open Question 3).

**(g) Deployment + PVC: redis**, 1 replica, image `redis:7-alpine` (same pinned tag `compose.prod.yaml:80`), `command: ["redis-server", "--appendonly", "yes"]` unchanged from compose, PVC mounted at `/data`. Confirmed via assignment table: "Deployment + PVC | redis" (explicitly not a StatefulSet, unlike postgres) — deliberately kept exactly as the table specifies.

**(h) Services × 4**, all `ClusterIP` (assignment: "ClusterIP for all. The database is never a NodePort or LoadBalancer") — `backend` (port 8000), `frontend` (port 8080), `postgres` (port 5432), `redis` (port 6379). Object/Service names reused exactly from the existing compose service names, deliberately — `docs/PARALLEL-WORK-PLAN.md` names no separate k8s-specific naming scheme beyond "StatefulSet (postgres, per `PARALLEL-WORK-PLAN.md`'s own naming)," and keeping Service names identical to compose service names means the `DATABASE_URL`/`REDIS_URL` connection strings translate to Kubernetes completely unchanged (`@postgres:5432`, `redis://redis:6379/0`) — no compose-vs-k8s divergence to track. No separate headless governing Service for the postgres StatefulSet — at replica 1 there's no need for per-pod DNS, and the assignment's literal "Service × 4" count leaves no room for a 5th.

**(i) Ingress**, single host, `pathType: Prefix` — `/` → `frontend:8080`, `/api` → `backend:8000` (assignment verbatim). No path rewrite needed on either rule: backend's real routes are already mounted at `/api/complaints`, `/api/stats`, etc. (`docs/CONTRACTS.md`), so the Ingress can forward the `/api` prefix straight through unmodified. Note (not a defect): `frontend/nginx.conf`'s own internal `location /api/` proxy (which compose relies on, since compose has no Ingress) becomes redundant once the Ingress does this split directly — both environments reach the same contract, they just differ in which proxy layer performs the `/api` split. Ingress controller — Open Question 1.

**(j) HorizontalPodAutoscaler**, on backend only (assignment: "On the backend — see below"), `autoscaling/v2`, `minReplicas: 2`, `maxReplicas: 10`, CPU `averageUtilization: 60`, `behavior.scaleDown.stabilizationWindowSeconds: 300`, `behavior.scaleUp.stabilizationWindowSeconds: 0` — copied verbatim from the assignment's own code block, not paraphrased.

**(k) VerticalPodAutoscaler**, on backend only, recommender mode (`updatePolicy.updateMode: "Off"`). **HPA/VPA conflict, stated here per the assignment's own instruction to explain it in notes, not just the manifest:** HPA scales replica count on CPU utilization; if VPA also ran in `Auto` mode adjusting the backend's CPU *request*, the two would fight over the same signal — VPA raising the request lowers computed utilization (usage ÷ request), which makes HPA scale in, which raises per-pod load, which makes VPA raise the request again, an oscillating loop with no stable point. Recommender-only mode breaks the loop: VPA only *suggests* (`kubectl describe vpa` prints Target/Lower/Upper bounds), a human reviews and manually updates `resources.requests` in the manifest, and HPA continues scaling on whatever request value is currently committed — decoupling "what should the request be" (VPA's job) from "how many replicas right now" (HPA's job). Note: VPA's own controller components (recommender/updater/admission-controller CRDs) are a cluster-level install, not a `k8s/base` manifest this phase produces — same category as `metrics-server`, which the assignment's own HPA deliverable line separately requires installing. Both are Verification-required install steps, not Deliverables of this spec.

**(l) PodDisruptionBudget**, `minAvailable: 1` on backend only (assignment/IMPLEMENTATION-PLAN.md verbatim).

**(m) Kustomize layout** — `k8s/base/` holds every object above with dev-safe, no-network-dependency defaults (`TRIAGE_PROVIDER=rules`, matching `compose.yaml`'s own dev default so a fresh `kubectl apply -k overlays/dev` never requires a real Gemini key to come up healthy). `overlays/dev` patches nothing provider-related (base default already suffices) but may patch the Ingress host and/or image references to locally-built tags for `k3d image import` (Open Question 2). `overlays/prod` patches `TRIAGE_PROVIDER` to `llm` and expects a real `GEMINI_API_KEY` to be injected into the Secret out-of-band (never committed) — mirroring `compose.prod.yaml`'s own unconditional requirement from Phase 10 exactly, though enforced differently: Compose's `${VAR:?msg}` fails at `docker compose config` time before any container exists; Kubernetes has no manifest-level equivalent of that fail-fast (see Open Question 4 — this is a real, disclosed gap, not silently matched). Per ADR 0003, `overlays/prod/kustomization.yaml`'s `images:` transformer carries no real tag in committed state — either omitted entirely or an obviously-fake placeholder — since the real commit-SHA tag is injected only by Phase 12's CI (`kustomize edit set image`), never hand-edited.

## Non-goals
- No CI/CD wiring — `cd.yml` deploying these manifests is Phase 12's scope entirely; nothing in `.github/workflows/` is touched here.
- No GitOps/Argo CD — bonus item, gated behind `docs/OPEN-DECISIONS.md` #10, still open; noted, not resolved, not built.
- No actual load-test run, no `kubectl get hpa -w` capture, no replicas-vs-load chart in this spec — that's Verification, performed once the manifests are implemented and approved, not drafted here.
- No zero-downtime-rollout **demonstration** under live load — bonus item per `docs/OPEN-DECISIONS.md` #10 ("zero-downtime rolling update under live load, +4"), still open; whether the cheap, non-bonus manifest fields (`maxSurge`/`maxUnavailable`/`preStop`/`terminationGracePeriodSeconds`) get added in this phase regardless is Open Question 5, not silently decided.
- No CD-only object gets built prematurely: no migration Job/initContainer is added without an explicit answer to Open Question 6 — schema bootstrapping stays exactly as manual as every other environment so far (dev compose, CI-to-come) unless resolved otherwise.
- No application-code changes — `backend/app/config.py`, `main.py`, etc. are read-only inputs to this phase, never edited (Open Question 4 flags a related gap but the fix, if any, is application code, out of this phase's file list).
- No digest pinning beyond what Phase 10 already decided is out of scope generally (`docs/OPEN-DECISIONS.md` #10) — image references here are tag-based (SHA tag, per ADR 0003), not digest-based.

## Open Questions

**1. Ingress controller for k3d.** The assignment specifies the Ingress *object* (routing rules) but not which controller processes it — k3d's own default bundled distribution (k3s) ships Traefik as its built-in ingress controller, requiring zero extra install. Alternative: install `ingress-nginx` separately.
**Recommendation:** Traefik — it's already present the moment a k3d cluster exists (same "no extra tool" precedent as the Kustomize-over-Helm decision), and the assignment's own Ingress requirement (`/` and `/api` prefix routing on one host) needs nothing `ingress-nginx`-specific (no complex rewrite annotations, etc.).
**Decided:** accepted as recommended. Traefik, k3d's bundled default — no separate ingress controller install.

**2. Dev overlay image sourcing.** `overlays/dev` needs a working image reference for a local `k3d apply` to actually schedule pods — unlike `overlays/prod`, which per ADR 0003 deliberately carries no real tag until CI injects one.
**Recommendation:** `overlays/dev`'s `images:` transformer points at locally-built tags matching compose's own dev image names (`civicpulse-backend:dev`, `civicpulse-frontend:dev`, from `compose.yaml`), loaded into the k3d cluster via `k3d image import` as a Verification step — no registry push needed for local dev, mirroring how compose already builds these locally rather than pulling from GHCR.
**Decided:** accepted as recommended. `overlays/dev` points at `civicpulse-backend:dev`/`civicpulse-frontend:dev`, imported into k3d via `k3d image import`, same tags compose's own dev build already produces.

**3. Exact `resources.requests`/`.limits` numbers.** The assignment mandates that requests exist (so the HPA has a denominator) but gives no numbers; `compose.prod.yaml` only ever specified `.limits` (backend 1.0 CPU/512M, frontend 0.5 CPU/128M, postgres 1.0 CPU/512M, redis 0.5 CPU/256M — confirmed directly), never `.requests`.
**Recommendation:** reuse Compose's existing limits unchanged as the k8s `.limits`, and set `.requests` at half of each (e.g. backend `250m`/`256Mi` request against `1000m`/`512Mi` limit) — a standard starting heuristic, explicitly *meant* to be wrong initially and corrected by the VPA recommendation loop the assignment itself describes ("record the requests you guessed... update your requests to match the recommendation").
**Decided:** accepted as recommended, with an explicit caveat carried into the Plan and every later reference to these numbers: `.limits` reused unchanged from `compose.prod.yaml`; `.requests` at half of each is a **guess, not a measurement** — the assignment's own 5-step VPA loop (record the guess → load test → `kubectl describe vpa` → update requests to match the recommendation → re-test) is what's expected to produce the real Target/Lower/Upper bound numbers and correct this guess. Nothing in this spec or the Plan below treats the halved numbers as final.

**4. No manifest-level equivalent of Phase 10's Compose fail-fast.** `${VAR:?msg}` makes `docker compose config`/`up` refuse to even resolve the file if `TRIAGE_PROVIDER`/`GEMINI_API_KEY` are unset — a static, pre-apply check. Kubernetes ConfigMaps/Secrets have no equivalent "required key" validation at the manifest layer: `kubectl apply` will happily accept an empty-string or placeholder `GEMINI_API_KEY` and the pod will start "successfully," silently reproducing the exact degraded-fallback failure mode Phase 10 fixed for Compose (confirmed still true — `backend/app/config.py:15`, `gemini_api_key: str = ""`, no validation, unchanged since Phase 10). Actually closing this gap would mean the app itself asserting a non-empty key at startup when `TRIAGE_PROVIDER=llm` — application code, outside this phase's manifest-only Deliverables.
**Recommendation:** do not silently leave this undocumented. Add a new numbered item to `docs/OPEN-DECISIONS.md` recording the gap (parallel to how #11 tracked the Prometheus port question) for a future phase to close in application code; this phase's manifests carry the placeholder Secret as scoped, with the gap disclosed rather than papered over.
**Decided:** accepted as a disclosed, deferred gap — not fixed in this phase. Recorded as `docs/OPEN-DECISIONS.md` #12 (see that file for the full write-up); nothing in `backend/app/` is touched by Phase 11.

**5. Rolling-update manifest fields (`maxSurge`/`maxUnavailable`/`preStop`/`terminationGracePeriodSeconds`).** These sit in the assignment's §3.3 text (between the Probes and HPA code blocks) but weren't named in this phase's Deliverables list, and the *demonstration* of zero-downtime under load is explicitly bonus (`docs/OPEN-DECISIONS.md` #10).
**Recommendation:** add the manifest fields now regardless (`maxSurge: 1`, `maxUnavailable: 0` on both Deployments, plus `terminationGracePeriodSeconds` and a `preStop` sleep on backend) — they cost nothing, match the assignment's own baseline text (not flagged there as bonus-only), and leave only the live-load *demonstration* itself gated behind #10, consistent with how #11 separated architecture from execution.
**Decided:** accepted as recommended, added now regardless of the bonus decision. `maxSurge: 1`/`maxUnavailable: 0` on both backend and frontend Deployments; `terminationGracePeriodSeconds` + a `preStop` sleep added on backend only (the one with in-flight request/DB-connection state worth draining — frontend is stateless nginx, no drain behavior to add). The live-load zero-downtime *demonstration* stays deferred behind `docs/OPEN-DECISIONS.md` #10.

**6. Schema bootstrapping on a fresh cluster.** No environment built so far (dev compose, this project's planned CI) has ever automated `alembic upgrade head` — it has always been a documented manual step. The readiness probe only checks Postgres/Redis *reachability* (`health.py:30-31`), not schema existence, so a fresh `kubectl apply -k overlays/dev` could report every pod "Ready" while the backend 500s on every real request against an empty database — meaning "brings the whole stack up healthy" (`IMPLEMENTATION-PLAN.md`'s own "done looks like" line) isn't actually true without migrations run somewhere.
**Recommendation:** an `initContainer` on the backend Deployment's pod template running `alembic upgrade head` before the main container starts — this doesn't add a new top-level object to the assignment's counted list (Namespace/Deployment×2/StatefulSet/Deployment+PVC/Service×4/Ingress/ConfigMap/Secret/HPA/VPA/PDB all stay exactly as enumerated; an initContainer is a field within the existing backend Deployment, not a new Kubernetes kind), and matches Kubernetes-native practice for this exact problem better than a manual `kubectl exec` step would.
**Decided:** accepted as recommended. Backend Deployment's pod template gets an `initContainer` (same `backend` image, override command to `alembic upgrade head`, reusing the same `DATABASE_URL` Secret) that must exit 0 before the main container starts.

**7. Ingress hostname.** No real DNS domain exists for a local/student k3d setup.
**Recommendation:** a single fixed local hostname, e.g. `civicpulse.local`, for both overlays, resolved via a manual `/etc/hosts` entry documented in the overlay READMEs — the assignment only requires "on one host," any host satisfies it.
**Decided:** accepted as recommended. `civicpulse.local` for both overlays, via a manual `/etc/hosts` entry documented in `k8s/overlays/dev/README.md` and `k8s/overlays/prod/README.md`.

## Verification required
Run against a real k3d cluster, exact commands, real output pasted in As-Built (not summarized):
1. `k3d cluster create civicpulse` (or confirm an existing cluster is up) — `kubectl cluster-info`
2. `k3d image import civicpulse-backend:dev civicpulse-frontend:dev -c civicpulse` (Open Question 2)
3. `kubectl kustomize k8s/overlays/dev` — dry-run manifest build succeeds, no YAML errors, before ever touching the cluster
4. `kubectl apply -k k8s/overlays/dev`
5. `kubectl get pods -n civicpulse -w` until backend/frontend show 2/2 Running with readiness passing, postgres/redis show 1/1 Running
6. `kubectl get svc -n civicpulse` — 4 ClusterIP services, no NodePort/LoadBalancer
7. `kubectl get pvc -n civicpulse` — postgres and redis PVCs both `Bound`
8. `kubectl get configmap,secret -n civicpulse -o yaml` — confirm Secret carries only placeholder values as committed (never a real key pasted into a live cluster used for this evidence capture)
9. `curl http://civicpulse.local/` (expect the frontend's `index.html`) and `curl http://civicpulse.local/api/stats` (expect a real JSON response, not 404/500 — proves both the Ingress split and, if Open Question 6 is resolved as recommended, the migration initContainer)
10. `kubectl delete pod <postgres-pod> -n civicpulse`, wait for the StatefulSet to recreate it, re-query a previously-seeded row — proves the persistence contract (`docs/CONTRACTS.md`: "deleting the Postgres pod must preserve every row")
11. Install `metrics-server` (if not already present in the k3d distribution) and confirm `kubectl top pods -n civicpulse` returns real numbers, not an error
12. `kubectl get hpa -n civicpulse` — confirm it shows a real `<current>/60%` (not stuck at `<unknown>/60%`, which the assignment names as the classic missing-`resources.requests` bug)
13. Install VPA components, `kubectl get vpa -n civicpulse`, `kubectl describe vpa backend-vpa -n civicpulse` — confirm it produces Target/Lower/Upper bound recommendations (even if the numeric values themselves are only meaningful after a load test, which is out of scope for this spec's own verification per Non-goals)
14. `kubectl kustomize k8s/overlays/prod` — dry-run build succeeds and confirms no real tag/secret value is embedded (Open Question 4/ADR 0003)
15. `kubectl delete -k k8s/overlays/dev` (or `kubectl delete namespace civicpulse`) — clean teardown, no orphaned PVCs left un-noted

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md`, the assignment's §3.3 text, or is underspecified beyond what's captured in the Open Questions above, stop and ask — do not silently resolve.

## Plan

No manifest YAML exists yet — `k8s/base/`, `k8s/overlays/dev/`, `k8s/overlays/prod/` still contain only their one placeholder `README.md` each (re-confirmed directly at Plan-drafting time, unchanged since the spec draft). This section describes what each file will contain and the order files get written/applied/verified in — not the files themselves.

**File list, in the order they'll be written** (dependency order: objects other objects reference come first):

**`k8s/base/` — 12 files:**

1. **`namespace.yaml`** — the `civicpulse` Namespace. First, because every other object's `metadata.namespace: civicpulse` depends on it existing.

2. **`configmap.yaml`** — `civicpulse-config`: `REDIS_URL=redis://redis:6379/0`, `TRIAGE_PROVIDER=rules` (base default), `POSTGRES_USER=civicpulse`, `POSTGRES_DB=civicpulse` (matching `.env.example`'s own dev-visible defaults, not secrets). Written before any Deployment/StatefulSet references it via `envFrom`/`valueFrom`.

3. **`secret.yaml`** — `civicpulse-secret`, `type: Opaque`, three keys all carrying **placeholder** string values (never a real password/key committed): `POSTGRES_PASSWORD: "changeme"`, `GEMINI_API_KEY: "changeme"`, `DATABASE_URL: "postgresql+psycopg://civicpulse:changeme@postgres:5432/civicpulse"` (the composed form — mechanically required per Deliverable (c)'s reasoning, kept consistent with the placeholder password above so the placeholder Secret is at least internally coherent, never intended to be `kubectl apply`'d unmodified against a real deploy). Written alongside the ConfigMap, before anything consumes it.

4. **`postgres.yaml`** — StatefulSet `postgres` (1 replica, image `postgres:16-alpine`, `serviceName: postgres`, env from the ConfigMap (`POSTGRES_USER`, `POSTGRES_DB`) and Secret (`POSTGRES_PASSWORD`), `volumeClaimTemplates` → one PVC for `/var/lib/postgresql/data`, `resources.requests`/`.limits` per Open Question 3's guessed halved values against Compose's existing 1.0 CPU/512M limit) + Service `postgres` (ClusterIP, port 5432) in the same file — the StatefulSet and its own governing Service are one unit. Written before backend, since backend's `initContainer` and readiness both depend on Postgres existing (not necessarily *ready* yet — Kubernetes doesn't order Pod scheduling by readiness across separate objects, only the app's own retry/probe behavior handles that — but the object must exist for DNS to ever resolve).

5. **`redis.yaml`** — PersistentVolumeClaim `redis-data` + Deployment `redis` (1 replica, image `redis:7-alpine`, `command: ["redis-server", "--appendonly", "yes"]` unchanged from compose, volume mount at `/data` from the PVC — a standalone PVC object here, not `volumeClaimTemplates`, since that field is StatefulSet-only and redis is deliberately a Deployment per the assignment table) + Service `redis` (ClusterIP, port 6379) in the same file, `resources` per Compose's 0.5 CPU/256M limit halved.

6. **`backend.yaml`** — Deployment `backend`: 2 replicas, container port 8000, `envFrom` the ConfigMap plus individual `valueFrom.secretKeyRef` for `DATABASE_URL` and `GEMINI_API_KEY`, `resources.requests`/`.limits` (1.0 CPU/512M limit halved per Open Question 3), all three probes as scoped in Deliverable (d), `initContainer` (Open Question 6 decision — same `backend` image, `command: ["alembic", "upgrade", "head"]`, same `DATABASE_URL` Secret key), `strategy.rollingUpdate: {maxSurge: 1, maxUnavailable: 0}`, `terminationGracePeriodSeconds` + a `preStop` sleep (Open Question 5 decision) + Service `backend` (ClusterIP, port 8000) in the same file. Written after Postgres/Redis/ConfigMap/Secret since its `initContainer` actively depends on Postgres being reachable to succeed (not just exist).

7. **`frontend.yaml`** — Deployment `frontend`: 2 replicas, container port 8080, no env vars needed (frontend's runtime config is nginx-proxy-based per ADR 0002, not env-injected), `resources` per Compose's 0.5 CPU/128M limit halved, single reused `httpGet: {path: /, port: 8080}` probe for both liveness and readiness (Deliverable (e) reasoning — no startup probe, no DB dependency to differentiate), `strategy.rollingUpdate: {maxSurge: 1, maxUnavailable: 0}` (Open Question 5 — no `preStop`/extended grace period needed, nginx has no connection-draining state worth adding beyond the default) + Service `frontend` (ClusterIP, port 8080) in the same file.

8. **`ingress.yaml`** — single Ingress, `ingressClassName: traefik` (Open Question 1 decision), host `civicpulse.local` (Open Question 7), two `pathType: Prefix` rules: `/` → `frontend:8080`, `/api` → `backend:8000`, no rewrite annotations (Deliverable (i) reasoning — backend routes are already mounted under `/api/...`).

9. **`hpa.yaml`** — HorizontalPodAutoscaler `backend-hpa`, `apiVersion: autoscaling/v2`, targeting the `backend` Deployment, copied verbatim from the assignment's own code block (`minReplicas: 2`, `maxReplicas: 10`, CPU `averageUtilization: 60`, `scaleDown.stabilizationWindowSeconds: 300`, `scaleUp.stabilizationWindowSeconds: 0`).

10. **`vpa.yaml`** — VerticalPodAutoscaler `backend-vpa`, targeting the `backend` Deployment, `updatePolicy.updateMode: "Off"` (recommender only, per Deliverable (k)'s HPA/VPA-conflict reasoning already written into the spec text above, not just this manifest).

11. **`pdb.yaml`** — PodDisruptionBudget `backend-pdb`, `minAvailable: 1`, selector matching the `backend` Deployment's pod labels.

12. **`kustomization.yaml`** — lists all 11 files above as `resources:`, common labels if any (none currently planned beyond what each manifest already sets), no `images:` transformer here (that's overlay-specific, since dev and prod need different image references per Open Question 2 / ADR 0003). Written last, since it references every file that must already exist.

**`k8s/overlays/dev/`:**

13. **`kustomization.yaml`** — `resources: [../../base]`, an `images:` transformer setting `backend`→`civicpulse-backend:dev`, `frontend`→`civicpulse-frontend:dev` (Open Question 2 decision, matching `compose.yaml`'s own dev image tags). No ConfigMap/Secret patch needed — base's `TRIAGE_PROVIDER=rules` default and placeholder Secret already work for a no-key local smoke test.

14. **`README.md` update** — replace the one-line placeholder with real instructions: `k3d cluster create`, `k3d image import`, the `/etc/hosts` entry for `civicpulse.local` (Open Question 7), `kubectl apply -k k8s/overlays/dev`.

**`k8s/overlays/prod/`:**

15. **`kustomization.yaml`** — `resources: [../../base]`, a ConfigMap patch (`TRIAGE_PROVIDER=llm`, per Phase 10's own prod requirement carried over), no `images:` transformer committed (or an obviously-fake placeholder tag) per ADR 0003 — the real SHA is injected only by Phase 12's CI via `kustomize edit set image`, never hand-written here.

16. **`README.md` update** — replace the placeholder with real instructions, explicitly noting (so nobody `kubectl apply`s this against a real cluster expecting it to work standalone) that the Secret must be replaced out-of-band with real values before a genuine prod apply, and that the image tag is CI-injected, not present in this committed file.

**Verification, run incrementally as files land, then the full list at the end:** apply Namespace → ConfigMap → Secret first and confirm with `kubectl get cm,secret -n civicpulse` before writing anything that references them; apply Postgres and Redis next and wait for `Running` before writing the backend manifest (so the `initContainer`'s first real run against a live Postgres is verified immediately, not batched with everything else); then backend, frontend, Ingress; then HPA/VPA/PDB last, since they reference the backend Deployment and are meaningless before it exists. The full 15-command Verification required list already in this spec is the final, complete pass run once all 16 files exist — not a substitute for the incremental checks above, which exist to localize a failure to the file that caused it rather than debugging the whole stack at once.

**Nothing here is uncertain** — every judgment call above resolves one of the 7 Open Questions already decided; anything not explicitly covered by a numbered Deliverable or Open Question is not touched by this Plan.

## As-Built
