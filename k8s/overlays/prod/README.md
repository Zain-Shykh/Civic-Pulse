Prod overlay on top of k8s/base.

Patches `TRIAGE_PROVIDER` to `llm` (mirrors `compose.prod.yaml`'s own
Phase 10 requirement). **This overlay is not deployable as committed:**

- `secret.yaml` (inherited from base) carries placeholder values only —
  `POSTGRES_PASSWORD`, `GEMINI_API_KEY`, and the composed `DATABASE_URL`
  must all be replaced out-of-band (e.g. `kubectl create secret generic
  civicpulse-secret --from-literal=... -n civicpulse --dry-run=client -o
  yaml | kubectl apply -f -`) before a real deploy. Never commit real
  values into this repo.
- No `images:` transformer is committed here (per
  `docs/adr/0003-deploy-by-sha.md`) — the real commit-SHA tag is injected
  only by CI (`kustomize edit set image ...`), never hand-written.
- There is currently no manifest-level check that `GEMINI_API_KEY` was
  actually replaced (`docs/OPEN-DECISIONS.md` #12, still open) — applying
  this overlay with the placeholder key still in place will start
  successfully and silently fall back to `rules:fallback` on every triage
  call. Confirm the real Secret is in place before trusting a green
  rollout.
