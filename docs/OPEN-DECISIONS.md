# Open Decisions

Everything below is left open by the assignment on purpose. Each is a question for the project owner, with the spec's own trade-off hints attached. Answering one may warrant an ADR later (the spec explicitly requires ADRs for the frontend runtime-config choice, deploy-by-SHA, PII/data-governance, and the provider interface).

## Resolved so far

| # | Decision | Answer |
|---|---|---|
| 1 | LLM provider | Google Gemini API, model `gemini-3.1-flash-lite` |
| 2 | Backend framework | FastAPI |
| 3 | K8s manifest tool | Kustomize |
| 4 | Local cluster | k3d |
| 5 | PII stance | Hybrid redaction — see `docs/adr/0004-pii-and-data-governance.md` (Accepted) |
| 6 | Repository / product name | CivicPulse (confirmed, no rename) |
| 7 | Rate-limiter algorithm | Fixed-window |
| 8 | Load-test tool | k6 |
| 9 | Scope given team status | Full assignment scope, self-paced timeline — see note in §9 below |

Still open: 10 (bonus items) — revisit before the CI/CD phase. 12 (K8s-layer fail-fast gap for `GEMINI_API_KEY`) — no owner phase assigned yet.

## 1. LLM provider choice — RESOLVED

**Decided:** Google Gemini API, model `gemini-3.1-flash-lite`. `LLMTriage` is built against Gemini's API; no need to also implement a Groq path.

**Free-tier verification (checked 2026-09-19), per the spec's own instruction to "cite what you actually saw":**

- Fetched `https://ai.google.dev/gemini-api/docs/pricing` directly (Google's own current pricing page, not a third-party aggregator). Its free-tier table lists **Gemini 3.1 Flash-Lite** with pricing explicitly marked **"Free of charge"** for input/output tokens — confirmed as free-tier eligible, not a paid-only preview model. (Gemini 2.5 Flash-Lite is also listed as free-tier eligible on the same page, as a fallback if 3.1 Flash-Lite is ever pulled from free tier.)
- Fetched `https://ai.google.dev/gemini-api/docs/rate-limits` directly. This page does **not** publish a static per-model free-tier RPM/TPM/RPD table — it states rate limits depend on account tier and directs to the live dashboard at `https://aistudio.google.com/rate-limit`. So the exact numeric limit could not be pulled from Google's own docs in this session.
- Cross-referenced several independent third-party trackers (not Google's own docs, so weaker evidence, but consistent with each other): they converge on **15 requests/minute, 1,000 requests/day** for Gemini 3.1 Flash-Lite's free tier, and confirm **no credit card / no Google Cloud billing account is required** to obtain a free-tier API key via Google AI Studio — matching the assignment's own claim about Gemini's free tier (§2.5).
- Confirmed from Google's own pricing page and corroborated by third-party sources: **on the free tier, Google may use inputs to improve its models** — this is the same caveat the assignment names, and it's what makes decision 5 (PII stance) a live decision rather than boilerplate.

**Action before Phase 1 backend work starts:** get an actual API key from Google AI Studio and read the live numbers at `aistudio.google.com/rate-limit` directly — that dashboard, not any doc page, is Google's authoritative source for the account's real current limits. Record whatever is seen there in this file, replacing the 15 RPM / 1,000 RPD figure above with the confirmed number.

Spec's own framing (§2.5), kept for reference:

- **Groq** — "recommended primary." OpenAI-compatible endpoint (official `openai` SDK works via `base_url`). Free tier gated only by rate limits, applied at the org level and per model, no credits/billing. Fast inference — "matters when a citizen is watching a spinner."
- **Google AI Studio (Gemini)** — "recommended alternative." Free tier on Flash/Flash-Lite, no credit card, generous daily allowance, native structured-output support. Caveat: on the free tier Google may use inputs to improve its models — complaints contain names, addresses, phone numbers, so this is a PII decision, not just a provider pick (feeds into decision 5 below, now live since Gemini is the chosen provider).
- **Ollama** — zero-dependency, no key, no network, no rate limit, no PII leaving the machine. Still required as the offline `OllamaTriage` implementation regardless of which hosted provider is chosen (§2.5 requires ≥3 implementations including it).
- **Other workable options**: OpenRouter free tier, Cloudflare Workers AI, Hugging Face Inference — not needed now that Gemini is chosen.

## 2. FastAPI vs Flask — RESOLVED

**Decided:** FastAPI. Reasoning (human's own): this is the spec's recommended path, and its auto-generated OpenAPI schema is what drives the frontend's typed API client — picking Flask would mean building that schema-to-client pipeline by hand for no offsetting benefit.

Spec (§2.2), kept for reference: "FastAPI + Pydantic v2 (recommended) or Flask (permitted; say so in the README)." FastAPI is recommended specifically because its OpenAPI schema is what the frontend's typed client is generated/checked against, and because Pydantic models validate both HTTP input and LLM output with one mental model.

## 3. Kustomize vs Helm — RESOLVED

**Decided:** Kustomize. Reasoning (human's own): matches the assignment's own §5.7 folder layout (`k8s/base` + `overlays/dev`, `overlays/prod`) exactly, with no extra templating tool to introduce.

Spec (§3.3), kept for reference: "Manifests, organised with Kustomize (base/ plus overlays/dev and overlays/prod). Helm is acceptable if you prefer it; say so in an ADR."

## 4. k3d vs kind — RESOLVED

**Decided:** k3d. Reasoning (human's own): faster iteration loop, and an easier local-registry story for the CI job that spins up an ephemeral cluster and deploys freshly built images into it.

Spec (§3.3), kept for reference: "Local cluster: k3d or kind — both run inside Docker, both are free, both work on a student laptop. A managed cloud cluster is not required and earns no extra marks."

## 5. PII handling stance — RESOLVED

**Decided:** Hybrid regex-based redaction (phone numbers, email addresses) applied to `text` only, before it reaches Gemini; `location` sent unmodified. Full detail, residual-risk statement, and layer ownership in `docs/adr/0004-pii-and-data-governance.md` (status: Accepted).

Spec (§2.5), kept for reference: "Citizen complaints contain names, addresses and phone numbers. Write the resulting PII decision into an ADR — redact before sending, send only the complaint body, or accept and document the exposure."

## 6. Repository / product name — RESOLVED

**Decided:** Keep "CivicPulse." No rename.

Spec (§1.2), kept for reference: "You may rename the product. Keep the contracts in §2 — they are what gets tested."

## 7. Rate-limiter algorithm — RESOLVED

**Decided:** Fixed-window. Reasoning (human's own): the requirement here is quota protection, not traffic smoothing — a fixed-window counter (`INCR` + `EXPIRE` in Redis) is simple and easier to test deterministically than a Lua-scripted token bucket, and quota protection is exactly what §2.4 Job 2 is for (stopping a bored user's `for` loop from exhausting the free-tier LLM quota, not shaping traffic curves).

Spec (§2.4, Job 2), kept for reference: "A fixed-window or token-bucket counter in Redis, keyed by client IP." Both satisfy the letter of the contract (429 + `Retry-After` on `POST /api/complaints`).

## 8. Load-test tool — RESOLVED

**Decided:** k6. Reasoning (human's own): matches the repo's own `load/k6-script.js` path already named in §5.7, and supports ramping virtual users — needed to actually produce the replicas-vs-load chart the rubric requires (§4-H), which a single-shot tool like `hey` doesn't model well.

Spec (§3.3, HPA deliverable), kept for reference: "generate load with k6 or hey."

## 9. Scope configuration given team status — RESOLVED

**Decided:** There is a real 2-person team on paper; a specific person will probably join, but he has not started and there is no confirmed date. When and if he does, slices from `docs/PARALLEL-WORK-PLAN.md` will be handed to him. Timeline: self-paced, ignoring the assignment's own conflicting 2-week/4-week framing (§5.1) — build to the full assignment scope (not the "split into two assignments" hedge) at whatever pace actually works.

**Residual risk, not eliminated by this decision:** Category A's partner-dependent line items (≥5 PRs with the partner's substantive review, the 35% commit-share floor, a real two-author merge conflict) still require the partner to actually contribute for a nontrivial stretch of time before submission — deciding "he'll join later" doesn't manufacture that history retroactively. If he joins late, those items may still need to be compressed into whatever time remains. Tracked in `docs/RUBRIC-CHECKLIST.md`.

Original framing kept for reference — spec (§5.1) offers three configurations, none of which is "solo-with-a-later-joiner":
- As written, 4 weeks, teams of 2.
- Teams of 3, frontend owned by one member, PR floor raised to 7, commit floor to 30% each.
- Split into two assignments: A1 = parts A–G (Docker/Compose, 110 marks), A2 = parts H–J (Kubernetes/CI-CD) on the same repo — "the safest option for a first run."

## 10. Bonus items to pursue (capped at +15)

Spec (§4, Bonus): zero-downtime rolling update under live load (+4), GitOps via Argo CD/Flux (+4), deploy-by-digest with Cosign signing (+3), Prometheus + Grafana dashboard (+2), OpenTelemetry tracing frontend→backend→LLM (+2).

**Question:** Attempt any bonus items, and if so which — or treat the 150-mark core as the entire scope until it's solid, given solo bandwidth?

## 11. Prometheus can't reach `/metrics` under the current compose shape

Raised during Phase 7b (`docs/specs/phase-07b-metrics.md`, Open Question 4).
`GET /metrics` exists and is verified working (`docs/specs/phase-07b-metrics.md`'s As-Built), but `compose.yaml`'s `backend` service publishes no host port at all today — only `frontend` has `ports: ["8080:8080"]`. A real, host-run Prometheus instance cannot scrape `/metrics` under the current compose shape without either publishing a backend port or running Prometheus itself as a compose service on the `edge` network.

This blocks the rest of RUBRIC-CHECKLIST.md's bonus line ("Prometheus scraping /metrics plus a Grafana dashboard, screenshot committed", +2) — the endpoint and instrumentation are done, the scraping/dashboard/screenshot piece isn't, and can't be until this is decided.

**Question:** publish a backend host port (weighing against §5.3's automatic-deduction list — a published *database or cache* port in `compose.prod.yaml` is a −8, but this is the backend API port in dev `compose.yaml`, a different case, not obviously covered by that penalty) versus running Prometheus as its own compose service on `edge`, reaching `backend` by service name the way `frontend` already does. Not decided here — candidate answer for whichever phase actually builds the Prometheus/Grafana pieces (Docker/Compose hardening, `docs/IMPLEMENTATION-PLAN.md` Phase 10, is the natural owner, but that's not decided either).

**Resolved (architecture only) — `docs/specs/phase-10-compose-hardening.md`, Open Question 1:** if the Prometheus/Grafana bonus item is ever pursued, Prometheus runs as its own compose service on the `edge` network, scraping `backend:8000/metrics` by Docker service name — no published host port on `backend`. Why: matches how `frontend` already reaches `backend`; Prometheus is pull-based, and keeping a scrape target network-internal rather than publicly exposed is standard practice regardless of environment. **Execution is still deferred to decision #10** ("which bonus items to pursue," still open) — no `prometheus` service, scrape config, or Grafana setup exists yet; this only fixes the shape it would take if #10 says yes.

## 12. No Kubernetes-manifest-level equivalent of Compose's `GEMINI_API_KEY` fail-fast

Raised during Phase 11 (`docs/specs/phase-11-kubernetes-manifests.md`, Open Question 4).

Phase 10 made `compose.prod.yaml` refuse to resolve at all (`docker compose config`/`up` errors before any container exists) if `TRIAGE_PROVIDER` or `GEMINI_API_KEY` is unset, via Compose's `${VAR:?msg}` interpolation syntax. Kubernetes Secrets/ConfigMaps have no equivalent construct — a Secret manifest is just a set of key/value pairs; `kubectl apply` has no notion of "this key must be non-empty" and will accept an empty string or an unreplaced placeholder value without complaint.

**What the gap is:** on Kubernetes, `kubectl apply -k overlays/prod` with an empty or still-placeholder `GEMINI_API_KEY` in the Secret succeeds silently. The backend pod starts, passes its liveness and readiness probes (neither checks the triage provider), and reports healthy. Every real `TRIAGE_PROVIDER=llm` triage call then fails Gemini's auth check, and `LLMTriage`'s broad exception handling (`backend/app/providers/triage/llm.py`, unchanged since Phase 10's analysis) falls back to `triaged_by = "rules:fallback"` for every single request, forever, with no operator-visible signal that anything is wrong — the exact silently-degraded failure mode Phase 10 closed for Compose, reopened here because the fix mechanism was Compose-specific.

**Why it can't be closed at the manifest layer:** Kubernetes' native validation primitives (`kubectl apply --validate`, CRD schema validation, admission webhooks) validate manifest *shape* (are the required fields present, are types correct), not the *runtime content* of a Secret's string value against an application-level rule like "non-empty when `TRIAGE_PROVIDER=llm`." Enforcing that requires either a custom admission webhook (real infrastructure, well beyond this phase's manifest-only scope) or, more simply, the application checking its own configuration at startup.

**What would close it:** an application-level startup check — e.g. in `backend/app/providers/triage/factory.py` or `backend/app/config.py` — that refuses to construct `LLMTriage` (crashes the process, which then fails its startup/liveness probe and crash-loops visibly in `kubectl get pods`, rather than starting "successfully") when `TRIAGE_PROVIDER=llm` and `GEMINI_API_KEY` is empty.

**Not decided or built here** — this is application code, out of scope for Phase 11's manifests-only Deliverables. Flagged for a future phase (not assigned an owner phase yet, same posture as #10/#11 before their owner phases were identified).
