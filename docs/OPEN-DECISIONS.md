# Open Decisions

Everything below is left open by the assignment on purpose. None of these are answered here — each is a question for the project owner, with the spec's own trade-off hints attached. Answering one may warrant an ADR later (the spec explicitly requires ADRs for the frontend runtime-config choice, deploy-by-SHA, PII/data-governance, and the provider interface).

## 1. LLM provider choice

Spec's own framing (§2.5):

- **Groq** — "recommended primary." OpenAI-compatible endpoint (official `openai` SDK works via `base_url`). Free tier gated only by rate limits, applied at the org level and per model, no credits/billing. Fast inference — "matters when a citizen is watching a spinner."
- **Google AI Studio (Gemini)** — "recommended alternative." Free tier on Flash/Flash-Lite, no credit card, generous daily allowance, native structured-output support. Caveat: on the free tier Google may use inputs to improve its models — complaints contain names, addresses, phone numbers, so this is a PII decision, not just a provider pick (feeds into decision 5 below).
- **Ollama** — zero-dependency, no key, no network, no rate limit, no PII leaving the machine. Slower on CPU, "noticeably worse at classification" — the buy-vs-host trade-off, measured rather than asserted. "If free-tier keys become a problem for anyone in your team, take this path — you lose no marks for it."
- **Other workable options**: OpenRouter free tier, Cloudflare Workers AI, Hugging Face Inference — acceptable if free and documented.

**Question:** Which provider is `LLMTriage` built against — Groq, Gemini, or an "other" option — and is Ollama the sole path (skipping a hosted provider entirely) an acceptable simplification here?

## 2. FastAPI vs Flask

Spec (§2.2): "FastAPI + Pydantic v2 (recommended) or Flask (permitted; say so in the README)." FastAPI is recommended specifically because its OpenAPI schema is what the frontend's typed client is generated/checked against, and because Pydantic models validate both HTTP input and LLM output with one mental model.

**Question:** FastAPI (per the stated recommendation) or Flask? If Flask, what replaces the "OpenAPI schema drives the typed frontend client" requirement (§2.1 "Required engineering")?

## 3. Kustomize vs Helm

Spec (§3.3): "Manifests, organised with Kustomize (base/ plus overlays/dev and overlays/prod). Helm is acceptable if you prefer it; say so in an ADR."

**Question:** Kustomize (the default path, matches the §5.7 repo layout as written) or Helm (requires its own ADR and a different `k8s/` layout than §5.7 shows)?

## 4. k3d vs kind

Spec (§3.3): "Local cluster: k3d or kind — both run inside Docker, both are free, both work on a student laptop. A managed cloud cluster is not required and earns no extra marks."

**Question:** k3d or kind, for both local dev and the ephemeral cluster spun up inside the `cd.yml` GitHub Actions runner?

## 5. PII handling stance

Spec (§2.5): "Citizen complaints contain names, addresses and phone numbers. Write the resulting PII decision into an ADR — redact before sending, send only the complaint body, or accept and document the exposure." This is explicitly named as one of the four required ADRs (§4, Category J) and directly depends on decision 1 (which provider, and whether that provider's free tier uses inputs for training).

**Question:** Which stance — (a) redact PII from complaint text before it reaches any hosted LLM, (b) send only the complaint body and accept whatever residual PII is embedded in the free text, or (c) accept and explicitly document the exposure? This gates what `LLMTriage` is allowed to send over the wire.

## 6. Repository / product name

Spec (§1.2): "You may rename the product. Keep the contracts in §2 — they are what gets tested." The current repo folder is `assign_1`; the assignment's own layout example uses `civicpulse/` as the root folder name.

**Question:** Keep "CivicPulse" as the product/repo name, or rename? (Contracts in `docs/CONTRACTS.md` are unaffected either way.)

## 7. Rate-limiter algorithm

Spec (§2.4, Job 2): "A fixed-window or token-bucket counter in Redis, keyed by client IP." Both satisfy the letter of the contract (429 + `Retry-After` on `POST /api/complaints`); they differ in burst behaviour and implementation complexity.

**Question:** Fixed-window (simpler, allows a burst at window boundaries) or token-bucket (smoother, slightly more Redis logic)?

## 8. Load-test tool

Spec (§3.3, HPA deliverable): "generate load with k6 or hey."

**Question:** k6 (JS-based, richer scripting, matches the `load/k6-script.js` path already named in §5.7) or hey (single static binary, simpler but less expressive)? Given §5.7 already names `load/k6-script.js`, k6 looks like the path of least resistance unless there's a reason to deviate.

## 9. Scope configuration given solo status

Spec (§5.1) offers three configurations, none of which is "solo":
- As written, 4 weeks, teams of 2.
- Teams of 3, frontend owned by one member, PR floor raised to 7, commit floor to 30% each.
- Split into two assignments: A1 = parts A–G (Docker/Compose, 110 marks), A2 = parts H–J (Kubernetes/CI-CD) on the same repo — "the safest option for a first run."

None of these directly addresses building solo with a possible late-joining partner. Category A (collaboration, 15 marks) assumes two people throughout (partner PR reviews, commit-share floor, a merge conflict between two contributors, a viva on a partner's code).

**Question:** Is there course guidance for solo students (e.g. a modified Category A rubric, or explicit permission to treat those 15 marks as forfeit), or should the project just be built to the full two-person spec and hope a partner joins in time to backfill collaboration evidence? Also worth deciding: attempt the assignment as written in full, or informally target the "split into two assignments" scope order (A–G first, fully solid, before touching H–J) as a risk hedge?

## 10. Bonus items to pursue (capped at +15)

Spec (§4, Bonus): zero-downtime rolling update under live load (+4), GitOps via Argo CD/Flux (+4), deploy-by-digest with Cosign signing (+3), Prometheus + Grafana dashboard (+2), OpenTelemetry tracing frontend→backend→LLM (+2).

**Question:** Attempt any bonus items, and if so which — or treat the 150-mark core as the entire scope until it's solid, given solo bandwidth?
