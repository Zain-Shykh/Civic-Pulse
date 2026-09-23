# ADR 0004: PII and data governance for the hosted LLM call

## Status

Accepted

## Context

`LLMTriage` (`docs/adr/0001-provider-interface.md`) sends citizen-submitted complaint text to Google's Gemini API (`gemini-3.1-flash-lite`) for classification. That free-text field is not sanitized of personal information by anything upstream — per the DB schema (`docs/CONTRACTS.md`), `text` is 10–2000 characters of free-form citizen input, and `location` and `reporter_contact` are separate fields that may or may not also be embedded in the free text itself. Realistically, citizens will write things like "burst main flooding Ahmed's shop on Street 12, call 0300-xxxxxxx" directly into the complaint body — names, addresses, and phone numbers routinely end up inside the very text that gets sent for triage.

**What we verified about Gemini's free tier** (`docs/OPEN-DECISIONS.md` #1, checked 2026-09-19 directly against `ai.google.dev/gemini-api/docs/pricing`): the free tier we're using is confirmed to let Google use submitted inputs to improve its models. This is not a hypothetical caveat — it's the specific tier this project is built on, because the free tier is what makes the assignment's zero-cost requirement work at all.

**What actually leaves the machine, today, with no mitigation:** the full complaint `text` field, verbatim, plus the `location` field, sent over HTTPS to Gemini's API for every complaint that goes through `LLMTriage` (i.e., every complaint, unless `TRIAGE_PROVIDER` is set to `ollama` or `rules`). `reporter_contact` is not currently sent (it isn't part of the `TriageProvider.triage(text, location)` call signature per `docs/CONTRACTS.md`), but PII embedded inside the free-text `text` field itself is sent regardless, because nothing currently distinguishes "the complaint" from "PII incidentally written inside the complaint."

## Decision

**Hybrid: regex-based redaction of phone numbers and email addresses in `text`, `location` sent unmodified.**

Before `LLMTriage` sends a request to Gemini, it runs `text` through a redaction pass:

- Detectable phone-number patterns are replaced with a fixed placeholder, e.g. `[REDACTED-PHONE]`.
- Detectable email-address patterns are replaced with a fixed placeholder, e.g. `[REDACTED-EMAIL]`.
- Whenever a redaction actually fires, log a structured event recording *that* a redaction happened and *which category* (phone / email) and a count — **never the matched substring, never the original value**. Same discipline as "never log the API key" (`CLAUDE.md`, §5.3-adjacent non-negotiables), extended to PII: the fact of redaction is observability data; the redacted value itself is exactly what we're trying to keep out of any log or third party.
- `location` is sent to Gemini **unmodified**. `TriageProvider.triage(text, location)` requires it for triage quality (a street name plausibly affects urgency/category judgement — e.g. proximity to a hospital or school), and it is typically street-level ("Street 12"), not a full postal address with a name attached — a materially smaller exposure than the free-text body.
- The redacted copy is what `LLMTriage` sends over the wire. The database record (`docs/CONTRACTS.md` schema, `text` column) always stores the citizen's original, unredacted submission — redaction is a property of the outbound Gemini call, not of what CivicPulse persists or displays on its own dashboard. Nothing about this decision touches storage or the operator-facing views.

**Layer ownership:** this is a **provider-layer concern**, not a general sanitization rule. The redaction helper belongs in `backend/app/providers/triage/` (used specifically by `LLMTriage`, immediately before constructing the outbound request) — not in `services/`, not applied to what `OllamaTriage` or `RuleBasedTriage` receive (neither sends data outside the machine, so neither needs it), and not applied anywhere text is read back from the repository layer. Phase 2/3 scaffolding should create this as a small, provider-scoped module (e.g. `providers/triage/redaction.py`), not a project-wide text-sanitization utility.

## Consequences

**What this does not solve — stated explicitly, not buried:**

- **Names typed into free text are not caught.** "Ahmed's shop" sends "Ahmed" to Gemini unchanged. Regex has no concept of a name; this would require NER (named-entity recognition), which is out of scope for this decision.
- **A citizen who writes their own precise address into the complaint body is not caught.** Only `location` is treated as address-shaped and it isn't touched (by design, per the Decision above); a full address embedded in `text` (e.g. "I live at House 12, Street 4, near the mosque") passes through unmodified, same as a name would.
- **Regex-based phone/email detection has real false negatives.** An unusually formatted number (e.g. spelled out, split across words, using an unexpected separator) will not match and will be sent unredacted.
- **Regex-based detection also has false positives.** A non-phone-number string that happens to match a digit-grouping pattern (e.g. a reference number, a house number sequence) could be redacted unnecessarily — a availability/quality cost, not a privacy cost, but worth naming since it can degrade triage input.

**Why this residual risk is accepted rather than solved:** a full NER-based PII scrubber (the only realistic way to catch names and free-form addresses) is out of scope for a free-tier academic project processing non-production, fictional/seeded complaint data (`docs/CONTRACTS.md` seed requirement — ≥30 *realistic but fabricated* complaints). The cost of building and validating a proper NER pass is disproportionate to the actual data at risk here. This justification is scoped to this project as submitted; it would not hold for a real deployment handling real citizens' real complaints, where Option A/full redaction or a no-training-data paid tier would be the correct bar, not this one.

**Operational consequence:** the redaction pass adds a small amount of provider-layer logic and a structured logging point, but no new dependency beyond the standard library's `re` module — no NER model, no third-party PII-detection service, keeping `LLMTriage` fast and dependency-light, consistent with the 10-second timeout budget (`docs/CONTRACTS.md`, AI layer engineering requirements).

## Alternatives considered

- **Full redaction / NER-based scrubbing (would fully address Option A from the original draft of this ADR):** rejected as disproportionate — see Consequences above. Left as the documented upgrade path if this project ever needed to handle real citizen data.
- **Truncation-only or "reasonable effort" scrubbing with no specific pattern targeting:** rejected as strictly worse than the chosen hybrid for the same implementation cost — targeting phone numbers and emails specifically catches the two most mechanically detectable, highest-confidence PII categories at effectively the same cost as vaguer truncation, without discarding potentially triage-relevant context the way blind truncation would.
- **Accept and document with zero mitigation:** rejected as the sole answer — cheap and honest, but leaves the two most easily-caught PII categories (phone numbers, emails) exposed for free, when a two-regex pass removes most of that exposure at near-zero cost. The accept-and-document posture survives in this decision only for what the hybrid deliberately doesn't catch (names, embedded addresses), stated above, not as the entire policy.
