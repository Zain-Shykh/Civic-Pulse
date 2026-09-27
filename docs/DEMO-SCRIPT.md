# Demo video shot-list

A scene-by-scene script for the §J demo video (≤5 minutes, both partners
speaking). This is a script/outline only — no recording exists yet
(`docs/RUBRIC-CHECKLIST.md`'s video row stays `[ ]` until one does). Every
command below is real and already-verified elsewhere in this repo; nothing
here is aspirational. Each scene cites where its evidence was actually
produced, so whoever records this reads the real prior output first rather
than improvising the command live and hoping it repeats.

Six scenes, ≈45s each, budgeted to fit inside 5 minutes with a few seconds of
slack for transitions.

## Scene 1 — Clean clone → running system (0:00–0:45)

**Speaker:** Partner A.

**On screen:** a terminal, starting from an empty directory.

**Commands** (the real, verified quickstart —
`docs/specs/phase-13-documentation-closeout.md`'s As-Built, "Real quickstart
verification" section):
```
git clone -b dev https://github.com/Zain-Shykh/Civic-Pulse.git
cd Civic-Pulse
cp .env.example .env
docker compose up -d --build
```
While containers build/start, cut to the pasted real output from that
As-Built:
```
$ docker compose ps
NAME                              STATUS
civicpulse-clonetest-backend-1    Up (healthy)
civicpulse-clonetest-frontend-1   Up (healthy)
civicpulse-clonetest-postgres-1   Up (healthy)
civicpulse-clonetest-redis-1      Up (healthy)
```
**Narration:** one command, four containers, all healthy — including the
one-shot `migrate` service that runs `alembic upgrade head` automatically
before `backend` starts (`compose.yaml`'s `migrate`/`backend` services,
`docs/specs/phase-13-documentation-closeout.md` As-Built Fix 2). State the
warm-Docker-cache caveat in one sentence, exactly as `README.md` and the
As-Built already do: this machine's image cache wasn't empty, so this proves
the compose files and `.env.example` are internally consistent, not a
true first-ever pull.

## Scene 2 — AI triage (0:45–1:30)

**Speaker:** Partner B.

**On screen:** the frontend Submit form, then the returned JSON / dashboard row.

**Commands** (same shape as the real verified call in the Phase 13 As-Built):
```
curl -s -X POST http://localhost:8080/api/complaints \
  -H "Content-Type: application/json" \
  -d '{"text":"Streetlight out on Elm St","location":"Elm St"}'
```
Real prior output to reference on screen:
```
{"category":"streetlights","priority":"normal","triaged_by":"rules", ...}
```
**Narration:** with `TRIAGE_PROVIDER=rules` (the dev default), the
`RuleBasedTriage` provider classifies the free text deterministically —
category, priority and a one-line summary, persisted and shown on the
dashboard. Point at `triaged_by` and `used_fallback: false` in the response
as the observability fields that prove which provider actually ran.

## Scene 3 — Fallback (1:30–2:15)

**Speaker:** Partner A.

**On screen:** a terminal call against a triage provider forced to fail,
then `GET /api/meta/providers`.

**Commands** (the real fallback-counter demonstration —
`docs/specs/phase-07b-metrics.md:291-298`):
```
curl -s http://localhost:8080/api/meta/providers   # before
curl -s -X POST http://localhost:8080/api/complaints -d '{...}'   # provider forced to fail
curl -s http://localhost:8080/api/meta/providers   # after
```
Real prior output to reference:
```
before: 0.0
POST status: 201 triaged_by: rules:fallback used_fallback: True
after: 1.0
```
**Narration:** the LLM call didn't just error out — `LLMTriage` retries once,
then falls back to `RuleBasedTriage` and still returns a real `201`, tagging
the row `rules:fallback` (`docs/TRIAGE.md`, "Fallback to `RuleBasedTriage`").
`GET /api/meta/providers`'s `recent_outcomes` list (`docs/CONTRACTS.md` §2.2)
is the live surface for spotting a rising fallback share in production.

## Scene 4 — Network isolation failing (2:15–3:00)

**Speaker:** Partner B.

**On screen:** a terminal, `docker compose exec` against the running stack.

**Commands** (the real, already-captured evidence —
`docs/specs/phase-10-compose-hardening.md:74-85`):
```
docker compose exec frontend ping -c 2 postgres
docker compose exec frontend ping -c 2 redis
```
Real prior output:
```
ping: bad address 'postgres'
ping: bad address 'redis'
```
**Narration:** this is a failing command shown as evidence of correct
design. `frontend` sits only on the `edge` network; `postgres`/`redis` sit
on `internal` (`internal: true`, no route to the outside world). The
failure is a DNS resolution failure, not just "no route" — `frontend` can't
even resolve the service name, because it was never placed on that network
at all.

## Scene 5 — HPA scaling (3:00–4:00)

**Speaker:** Partner A.

**On screen:** `kubectl get hpa -n civicpulse -w` during a k6 load run.

**Commands** (the real captured scale-out —
`docs/specs/phase-11b-failfast-and-vpa-verification.md:257-303`):
```
k6 run load/k6-script.js
kubectl get hpa -n civicpulse -w
```
Real prior output to reference on screen (Run 2, after the VPA-corrected
request):
```
backend-hpa   Deployment/backend   cpu: <unknown>/60%   2   10   2    31m
backend-hpa   Deployment/backend   cpu: 82%/60%         2   10   3    32m
...
backend-hpa   Deployment/backend   cpu: 2%/60%           2   10   2    51m
```
**Narration:** under sustained load past the 60% CPU target, HPA scaled
`2 → 3` within one 20s poll interval once real metrics were available
(`scaleUp.stabilizationWindowSeconds: 0`); after load stopped, it held the
extra replica for the full 300s `scaleDown.stabilizationWindowSeconds`
before releasing it back to the `minReplicas: 2` floor — fast to add
capacity, deliberately slow to remove it.

## Scene 6 — Rollback (4:00–4:50)

**Speaker:** Partner B.

**On screen:** a terminal against the k8s cluster.

**Commands** (both mechanisms the assignment names, `docs/RUNBOOK.md`'s
"Roll back" section — procedure only, not yet executed on camera before this
recording):
```
# Fast, imperative — the 3 a.m. answer
kubectl rollout undo deployment/backend -n civicpulse
kubectl rollout status deployment/backend -n civicpulse

# Declarative, auditable — the correct answer once the fire is out
cd k8s/overlays/prod
kustomize edit set image civicpulse-backend=ghcr.io/<owner>/civicpulse-backend:<previous-sha>
kubectl apply -k .
kubectl rollout status deployment/backend -n civicpulse
```
**Narration:** explain when each applies — `rollout undo` is immediate and
uses the Deployment's own revision history, but only works if the previous
ReplicaSet hasn't been garbage-collected; re-applying the previous SHA via
Kustomize is what actually happens in this project's real deploy pipeline
(`docs/adr/0003-deploy-by-sha.md`) and is the auditable, repeatable version
of the same rollback.

## Closing (4:50–5:00)

Both partners on screen. One sentence each on what they personally built.
