# Phase 5b: LLM triage provider
Status: not started
Depends on: Phase 5a (`base.py`'s `TriageProvider`/`TriageResult`, `factory.py`'s `_PROVIDERS` dict, `RuleBasedTriage` as the fallback target)
Reads first: `docs/CONTRACTS.md` §2.5 (AI layer), `docs/adr/0001-provider-interface.md`, `docs/adr/0004-pii-and-data-governance.md`, `docs/architecture/ARCHITECTURE.md` ("The LLM-egress trade-off"), `docs/OPEN-DECISIONS.md` #1 (Gemini provider choice), `docs/IMPLEMENTATION-PLAN.md` (Phase 5 section)

## Goal
Implement `LLMTriage`, the production `TriageProvider` backed by Google Gemini (`gemini-3.1-flash-lite`), satisfying `docs/CONTRACTS.md` §2.5's full set of engineering requirements for a network-calling provider — structured-output validation, a hard timeout, one bounded retry, fallback to `RuleBasedTriage` on exhausted retries, PII redaction before anything leaves the process, and no logged secrets — wired into the existing factory (ADR 0001) so `TRIAGE_PROVIDER=llm` becomes a real, selectable path instead of today's `KeyError`.

## Deliverables
Each line cites the source that justifies it. Nothing below is included without one.

1. `backend/app/providers/triage/llm.py` (rewritten from its Phase 2 stub) — `LLMTriage` implementing the `TriageProvider` Protocol (`base.py`, Phase 5a): calls Gemini `gemini-3.1-flash-lite`, requests structured output and validates the response against `TriageResult` regardless of what comes back, applies a 10-second hard timeout, retries exactly once with jitter and only on timeout/429/5xx (never on 400), and falls back to `RuleBasedTriage` when retries are exhausted.
   *Cite: `docs/CONTRACTS.md` §2.5, engineering requirements 1–4 (lines 98–101); `docs/OPEN-DECISIONS.md` #1 (Gemini, `gemini-3.1-flash-lite`, chosen provider); `docs/adr/0001-provider-interface.md`'s factory dict shape (`"llm": lambda: LLMTriage(...)`, a single class — the wrapper behavior lives inside `LLMTriage` itself, not a separate wrapped-provider pair, since ADR 0001 gives `"llm"` exactly one factory entry).*

2. `backend/app/providers/triage/redaction.py` (new) — a small, provider-scoped module that regex-redacts phone numbers and email addresses out of `text` before `LLMTriage` constructs its outbound request; `location` is passed through unmodified; a redaction event is logged only as a structured fact (category + count), never the matched substring.
   *Cite: `docs/adr/0004-pii-and-data-governance.md`, "Decision" section verbatim: "Before `LLMTriage` sends a request to Gemini, it runs `text` through a redaction pass" and "Layer ownership: this is a provider-layer concern... The redaction helper belongs in `backend/app/providers/triage/`... (e.g. `providers/triage/redaction.py`)."*

3. `backend/app/config.py` — add a `gemini_api_key` setting to `Settings`, sourced from the environment/`.env` only (already the pattern this file uses for `database_url`/`redis_url`). Checked directly: no Gemini-related field exists in `Settings` today.
   *Cite: `docs/CONTRACTS.md` §2.5 engineering requirement 6, "Never log the API key. Environment / Kubernetes Secret / GitHub Secrets only, never a file in the repo"; `CLAUDE.md`'s non-negotiables (committed key/token deductions).*

4. `backend/app/providers/triage/factory.py` — wire the `"llm"` key in `_PROVIDERS` to construct `LLMTriage`, replacing today's `KeyError` fallthrough for that value specifically. `"ollama"` is untouched (see Open Question 1).
   *Cite: `docs/adr/0001-provider-interface.md`'s factory dict shape; Phase 5a's own precedent of adding one key at a time to `_PROVIDERS` without touching the others.*

5. `backend/tests/test_llm_triage.py` (new) — provider-level tests against a fake/mocked Gemini transport, no live API calls, covering: a valid structured response round-trips into a `TriageResult`; a malformed/out-of-schema response is still caught by Pydantic validation (requirement 1); a timeout triggers the retry then, if still failing, the fallback; a 429/5xx does the same; a 400 is never retried; the mandatory Determinism test from `docs/CONTRACTS.md` line 106–108 ("given a provider that always raises, ... `triaged_by == "rules:fallback"`"), exercised at the provider level since `POST /api/complaints` doesn't exist until Phase 7 (see Non-goals, and Phase 5a's own precedent of testing this shape at the provider level); a prompt-injection attempt in `text` still yields a schema-valid `category` (requirement 7); redaction fires on phone/email patterns before the outbound request is built, and only a structured "redaction happened" event is observable, never the original value (ADR 0004).
   *Cite: `docs/CONTRACTS.md` §2.5 engineering requirements 1–4 and 7; the mandatory Determinism test (lines 106–108); ADR 0004's logging discipline; user instruction that CI must not depend on a live Gemini key/quota (see Open Question 3 for the exact test-double mechanism, deferred to Plan).*

## Non-goals
- `OllamaTriage` — Open Question 1 below proposes excluding it from this phase's scope regardless of how `docs/IMPLEMENTATION-PLAN.md`'s own wording is read; not built here either way until that's resolved.
- Redis content-hash caching of triage results (`docs/CONTRACTS.md` §2.5 engineering requirement 5) — already deferred, not by this spec's choice: `backend/app/providers/cache.py`'s own docstring states "The stats cache, rate limiter, and triage-result cache built on top of this client arrive in the Cache Layer phase, with their own spec" (Phase 8, `docs/IMPLEMENTATION-PLAN.md`). `LLMTriage` calls Gemini for every request in this phase with no deduplication; that gap is intentional and closes in Phase 8, not here.
- Full HTTP-level assertion of the mandatory Determinism test via a real `POST /api/complaints` — routes don't exist until Phase 7. `docs/IMPLEMENTATION-PLAN.md`'s own Phase 5 "Done looks like" line already scopes Phase 5's tests to direct provider instantiation, no HTTP, no DB; Deliverable #5 follows that precedent.
- `services/` orchestration, routes, or any wiring of `TriageProvider` into request handling — Phase 6/7.
- NER-based PII scrubbing, or redacting anything in `text` beyond phone numbers and email addresses, or touching `location` — `docs/adr/0004-pii-and-data-governance.md`'s "Consequences" section names this out of scope by decision (names, embedded addresses), not oversight.
- Verifying `gemini-3.1-flash-lite`'s actual live rate-limit numbers — `docs/OPEN-DECISIONS.md` #1 already flags this as its own outstanding action item, unrelated to this phase's fixed 10-second-timeout/one-retry design, which comes from `docs/CONTRACTS.md` directly rather than from the account's real quota.
- `OllamaTriage`'s stub content in `ollama.py` — untouched.
- Any change to `docs/CONTRACTS.md`'s `TriageProvider` Protocol shape (`name: str`, `triage(text, location) -> TriageResult`) — Open Question 2 below flags a real tension here but proposes working within the existing shape, not extending it, pending approval.

## Open Questions
Flagged rather than silently decided, per instruction. Do not proceed on any of these without a decision.

1. **Does this phase's scope include `OllamaTriage`, or `LLMTriage` only?**
   `docs/IMPLEMENTATION-PLAN.md`'s exact wording (Phase 5 section): *"5b — `LLMTriage`: Gemini client, hybrid PII redaction (ADR 0004) applied before any text leaves the process, timeout/retry/fallback-to-`RuleBasedTriage` wrapper (per `docs/CONTRACTS.md`), `triaged_by = "llm:gemini"` (`DEVIATIONS.md`)."* followed immediately by: *"`OllamaTriage` fits in 5b's slot too (same "external, needs a wrapper" shape) but is lower priority than getting `LLMTriage` correct — sequence within 5b when we get there."*
   This is genuinely ambiguous: the first sentence names `LLMTriage` alone as "5b"; the second says `OllamaTriage` "fits in 5b's slot too" but immediately hedges with "sequence... when we get there," which reads as deferred timing, not a hard requirement that both land in one spec/commit/PR.
   **Proposal for approval:** scope this spec (`phase-05b-llm-triage.md`) to `LLMTriage` only, and split `OllamaTriage` into its own `phase-05c-ollama-triage.md` spec later, following the same precedent Phase 5 itself already set by splitting 5a and 5b into separate specs despite both being "Phase 5." Reasoning: `LLMTriage` alone already carries real, citable complexity (redaction, timeout/retry/fallback, structured-output validation, a mandatory injection-guardrail test) — bundling in a second, network-calling provider with a different transport (local Ollama server, not a hosted API) would make one Plan section cover two materially different integrations, working against the "depth scales with the phase" discipline `CLAUDE.md` asks for. This does not decide `OllamaTriage`'s scope, only this spec's — reject this proposal and both providers can still be folded into one Plan if that's preferred.

2. **How does a per-call fallback outcome reach `triaged_by`, given `TriageProvider.name` is a single, static-looking attribute?**
   `docs/CONTRACTS.md` §2.5's code block declares `TriageProvider.name: str` — one attribute per provider instance — and `TriageResult` itself carries no `triaged_by` field (confirmed directly in `base.py`, Phase 5a). The established reading (Phase 5a's Open Question 1 resolution) is that `triaged_by` is populated from `TriageProvider.name` by whatever calls the provider, except that engineering requirement 4 requires the *fallback path specifically* to record `triaged_by = "rules:fallback"` (`docs/CONTRACTS.md` line 101) even when the provider that was actually configured is `LLMTriage`, whose `name` would otherwise read `"llm:gemini"`.
   Nothing in `docs/CONTRACTS.md` or the ADRs says how a single provider instance is supposed to report "this particular call fell back" through one static `name` string. Two ways to resolve it, neither citable, both left for Plan-stage decision:
   - `LLMTriage.name` is a plain instance attribute (not a class constant — nothing prevents this in Python, and Phase 5a's `RuleBasedTriage`/`SimulatedTriage` already use plain class-level assignment, not a frozen constant), and `LLMTriage.triage()` reassigns `self.name = "rules:fallback"` for the duration of/immediately after a call that fell back, then resets it. Works within the Protocol exactly as written; the mechanism itself (mutating `name` per-call) isn't documented anywhere, which is why it's flagged rather than just done.
   - The interface changes (e.g. `TriageResult` gains a `triaged_by` field, or `triage()` returns a tuple). Rejected as a default option here, not because it's technically worse, but because `CLAUDE.md` is explicit that changing a `docs/CONTRACTS.md` boundary "is a decision to flag, never a side-effect of an unrelated change" — this phase shouldn't quietly widen the Protocol.
   **Proposal for the Plan step: the first option (mutable `self.name`), no `CONTRACTS.md` change.** Flagging now because it's a real design decision this phase can't avoid, not because either answer is obviously wrong.

3. **Exact mechanism for testing the Gemini call path without a live API key/quota.**
   Per explicit instruction, CI cannot depend on a live Gemini key or quota, and Deliverable #5 already names the test file this implies. The exact mechanism — a fake HTTP transport, a monkeypatched `google-genai` client, or a small dependency-injected client seam inside `LLMTriage` — is left undecided here and proposed in the Plan step, per instruction ("your call, but this needs to be decided in Plan"). Note: `google-genai==2.24.0` is already a pinned dependency (`backend/pyproject.toml`), so no new dependency is implied regardless of which mechanism is chosen.

## Plan

## Verification required
- `python -m pytest backend/tests/test_llm_triage.py -v` — real pasted output, all tests passing, none making a live network call (confirm by running once with network deliberately unavailable inside the test container, or by asserting the test double was actually invoked — decided in Plan).
- `ruff check` / `mypy` on all touched files — real pasted output, clean.
- Manual confirmation that `TRIAGE_PROVIDER=llm` resolves via `get_triage_provider()` to an `LLMTriage` instance (paste the actual output).
- Manual confirmation that no API key literal appears in any diff or committed file (`git diff` / `grep` check, pasted).
- If a real Gemini API key is available at verification time: one real manual call recorded in As-Built, consistent with `docs/IMPLEMENTATION-PLAN.md`'s own Phase 5 "Done looks like" line ("a manual run against a live Gemini key produces a sane result; killing network access to the LLM provider provably falls back to `RuleBasedTriage` rather than 500ing"). If no key is available at that time, state that explicitly in As-Built rather than skipping the line silently.

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md`, `docs/adr/0001-provider-interface.md`, or `docs/adr/0004-pii-and-data-governance.md`, or is underspecified beyond what's already flagged under Open Questions above, stop and ask — do not silently resolve.

## As-Built
