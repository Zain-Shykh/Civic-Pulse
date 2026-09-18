# Open Decisions

Everything below is left open by the assignment on purpose. Each is a question for the project owner, with the spec's own trade-off hints attached. Answering one may warrant an ADR later (the spec explicitly requires ADRs for the frontend runtime-config choice, deploy-by-SHA, PII/data-governance, and the provider interface).

## Resolved so far

| # | Decision | Answer |
|---|---|---|
| 1 | LLM provider | Google Gemini API, model `gemini-3.1-flash-lite` |
| 9 | Scope given team status | Full assignment scope, self-paced timeline — see note in §9 below |

Still open: 2 (FastAPI vs Flask), 3 (Kustomize vs Helm), 4 (k3d vs kind), 5 (PII stance — now scoped to Gemini specifically), 6 (repo name), 7 (rate-limiter algorithm), 8 (load-test tool), 10 (bonus items).

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

Spec (§2.5): "Citizen complaints contain names, addresses and phone numbers. Write the resulting PII decision into an ADR — redact before sending, send only the complaint body, or accept and document the exposure." This is explicitly named as one of the four required ADRs (§4, Category J), and is now a live decision, not a hypothetical one — decision 1 fixed the provider as **Gemini**, whose free tier the spec says "may use your inputs to improve its models."

**Question:** Which stance — (a) redact PII from complaint text before it reaches Gemini, (b) send only the complaint body and accept whatever residual PII is embedded in the free text, or (c) accept and explicitly document the exposure? This gates what `LLMTriage` is allowed to send to Gemini over the wire, and is the actual content of the required PII ADR.

## 6. Repository / product name

Spec (§1.2): "You may rename the product. Keep the contracts in §2 — they are what gets tested." The current repo folder is `assign_1`; the assignment's own layout example uses `civicpulse/` as the root folder name.

**Question:** Keep "CivicPulse" as the product/repo name, or rename? (Contracts in `docs/CONTRACTS.md` are unaffected either way.)

## 7. Rate-limiter algorithm

Spec (§2.4, Job 2): "A fixed-window or token-bucket counter in Redis, keyed by client IP." Both satisfy the letter of the contract (429 + `Retry-After` on `POST /api/complaints`); they differ in burst behaviour and implementation complexity.

**Question:** Fixed-window (simpler, allows a burst at window boundaries) or token-bucket (smoother, slightly more Redis logic)?

## 8. Load-test tool

Spec (§3.3, HPA deliverable): "generate load with k6 or hey."

**Question:** k6 (JS-based, richer scripting, matches the `load/k6-script.js` path already named in §5.7) or hey (single static binary, simpler but less expressive)? Given §5.7 already names `load/k6-script.js`, k6 looks like the path of least resistance unless there's a reason to deviate.

## 9. Scope configuration given team status — RESOLVED

**Decided:** There is a real 2-person team on paper; the partner is not currently active but is expected to join later, at which point slices from `docs/PARALLEL-WORK-PLAN.md` will be handed to them. Timeline: self-paced, ignoring the assignment's own conflicting 2-week/4-week framing (§5.1) — build to the full assignment scope (not the "split into two assignments" hedge) at whatever pace actually works.

**Residual risk, not eliminated by this decision:** Category A's partner-dependent line items (≥5 PRs with the partner's substantive review, the 35% commit-share floor, a real two-author merge conflict) still require the partner to actually contribute for a nontrivial stretch of time before submission — deciding "he'll join later" doesn't manufacture that history retroactively. If he joins late, those items may still need to be compressed into whatever time remains. Tracked in `docs/RUBRIC-CHECKLIST.md`.

Original framing kept for reference — spec (§5.1) offers three configurations, none of which is "solo-with-a-later-joiner":
- As written, 4 weeks, teams of 2.
- Teams of 3, frontend owned by one member, PR floor raised to 7, commit floor to 30% each.
- Split into two assignments: A1 = parts A–G (Docker/Compose, 110 marks), A2 = parts H–J (Kubernetes/CI-CD) on the same repo — "the safest option for a first run."

## 10. Bonus items to pursue (capped at +15)

Spec (§4, Bonus): zero-downtime rolling update under live load (+4), GitOps via Argo CD/Flux (+4), deploy-by-digest with Cosign signing (+3), Prometheus + Grafana dashboard (+2), OpenTelemetry tracing frontend→backend→LLM (+2).

**Question:** Attempt any bonus items, and if so which — or treat the 150-mark core as the entire scope until it's solid, given solo bandwidth?
