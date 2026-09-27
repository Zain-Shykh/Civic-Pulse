# Runbook

Real operational procedures for this repository's actual current state — not an aspirational one. Where something described here (structured logging, see "Reading logs" below) isn't implemented yet, that's stated plainly rather than written as if it already existed.

## Deploy

**Local, Docker Compose (dev):**

```
cp .env.example .env   # fill in real values — see .env.example's own comments
docker compose up
```

**Local, Docker Compose (prod-shaped, for testing `compose.prod.yaml` itself):**

```
docker compose -f compose.prod.yaml up -d
```
`TRIAGE_PROVIDER` and `GEMINI_API_KEY` are required (`compose.prod.yaml`'s `${VAR:?msg}` syntax — Compose itself refuses to start if either is unset). `IMAGE_TAG` in `.env.example` defaults to `latest` for local testing only — `docs/adr/0003-deploy-by-sha.md` and the comment at the top of `compose.prod.yaml` are explicit that a real deployment never uses that default; CI always sets a real commit SHA.

**Kubernetes, dev (k3d):** `k8s/overlays/dev/README.md` has the full sequence (`k3d cluster create` → local image build → `k3d image import` → `kubectl apply -k k8s/overlays/dev`).

**Kubernetes, prod — the real path is automated, not manual:** a merge to `main` triggers `.github/workflows/cd.yml`'s `deploy-k8s` job, which sets the real commit SHA into `k8s/overlays/prod` via `kustomize edit set image` (in the CI job's own checkout — never committed, per that file's comment) and applies it. There is deliberately no hand-maintained image tag inside the committed `k8s/overlays/prod/kustomization.yaml` to keep in sync. To reproduce the same deploy manually against a real cluster (e.g. recovering from a CI outage):

```
cd k8s/overlays/prod
kustomize edit set image \
  civicpulse-backend=ghcr.io/<owner>/civicpulse-backend:<commit-sha> \
  civicpulse-frontend=ghcr.io/<owner>/civicpulse-frontend:<commit-sha>
kubectl apply -k .
kubectl rollout status deployment/backend -n civicpulse --timeout=180s
kubectl rollout status deployment/frontend -n civicpulse --timeout=180s
```

## Roll back

**Docker Compose (prod-shaped):** set `IMAGE_TAG` in `.env` to the previous known-good commit SHA (every image is tagged by SHA in GHCR, per `docs/adr/0003-deploy-by-sha.md` — there is always a specific previous tag to go back to, never a floating `latest`), then `docker compose -f compose.prod.yaml up -d` again.

**Kubernetes — two equivalent options:**
- Re-run the manual deploy sequence above with the previous SHA instead of the current one (`kustomize edit set image ... :<previous-sha>` then `kubectl apply -k`) — the most explicit option, and the one that matches how a forward deploy actually happens.
- `kubectl rollout undo deployment/backend -n civicpulse` / `deployment/frontend -n civicpulse` — the Kubernetes-native option, using the Deployment's own revision history (only works if the previous ReplicaSet hasn't been garbage-collected).

Either way, `kubectl rollout status` confirms the rollback completed the same way a forward deploy is confirmed.

## Reading logs

**What's actually there today:** plain stdout/stderr from FastAPI/uvicorn (backend) and nginx's access/error logs (frontend) — `docker compose logs -f backend` / `kubectl logs -n civicpulse deployment/backend -f` (swap `backend` for `frontend`/`postgres`/`redis` as needed). Individual providers log specific structured *events* today — e.g. `backend/app/providers/triage/redaction.py:38-41` logs `pii_redacted` with a category and count (never the matched value), and `backend/app/providers/triage/llm.py:106,112-115` logs `llm_triage_malformed_response`/`llm_triage_call_failed` — but these are individual `logger.info`/`logger.warning` calls, not a project-wide structured-JSON formatter.

**What's not there yet, stated plainly rather than glossed over:** `docs/RUBRIC-CHECKLIST.md` Category C's "Structured JSON logging to stdout with a propagated request_id" row is `[ ]` — no request-scoped `request_id` exists anywhere in this codebase yet, and log lines are whatever Python's default logging format produces, not JSON. This runbook describes what's real, not the aspirational shape.

**Metrics, not logs, for aggregate visibility:** `GET /metrics` (Prometheus text format — request count, latency histogram, triage latency, fallback counter, per `docs/CONTRACTS.md` §2.2) is real and instrumented (`app/main.py`'s `Instrumentator().instrument(app).expose(app)`, Phase 7b). No Prometheus/Grafana is deployed to scrape it yet (`docs/RUBRIC-CHECKLIST.md`'s Bonus section) — the endpoint exists, the dashboard doesn't.

## When triage starts failing

Read `docs/TRIAGE.md` first — this section only points at the relevant parts of it, doesn't re-explain them.

1. **Check `GET /api/meta/providers`** — the real-time observability surface (`docs/CONTRACTS.md` §2.2): which provider is active, and the last 20 triage outcomes (provider, latency ms, fallback y/n). A rising share of `"rules:fallback"` outcomes is the concrete signal that `LLMTriage` is failing and silently degrading, not the absence of any output.
2. **If `TRIAGE_PROVIDER=llm` and every result is `rules:fallback`:** the Gemini call itself is failing — check for `llm_triage_call_failed` log lines (`backend/app/providers/triage/llm.py:112-115`), which include the exception type and error code. Common causes: an invalid/expired `GEMINI_API_KEY` (should have failed at startup instead, per `factory.py:30-38` — see `docs/specs/phase-11b-failfast-and-vpa-verification.md`'s fail-fast check, but confirm the Secret actually holds a real value, not the committed placeholder), a Gemini-side outage or rate limit (429/5xx — these do get one jittered retry, `llm.py:52-58`, before falling back), or the `internal: true` network blocking egress entirely (see `docs/TRIAGE.md`/`docs/ENGINEERING-NOTES.md` Q7 — only the `backend` service has both `edge` and `internal` network membership; if that's misconfigured, every LLM call times out and falls back).
3. **If results look wrong but the provider itself is reachable:** confirm `TRIAGE_PROVIDER`'s actual runtime value (`GET /api/meta/providers` names it) — a deploy that quietly ended up on `rules` or `simulated` instead of `llm` isn't a "failure," it's a misconfiguration, and produces plausible-looking but non-AI results.
4. **Immediate mitigation while investigating:** nothing needs to change — `LLMTriage`'s built-in fallback already keeps the system serving triaged (if less accurate) results via `RuleBasedTriage` rather than 500ing. There is no "disable the LLM" switch to flip; the fallback path *is* that switch, automatically.
