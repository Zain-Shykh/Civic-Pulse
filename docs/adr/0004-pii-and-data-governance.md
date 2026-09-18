# ADR 0004: PII and data governance for the hosted LLM call

## Status

**DECISION PENDING — awaiting human input.** This document lays out the options and their trade-offs honestly, per instruction. It does not choose one. Do not treat any option below as selected until the human fills in a Decision section.

## Context

`LLMTriage` (`docs/adr/0001-provider-interface.md`) sends citizen-submitted complaint text to Google's Gemini API (`gemini-3.1-flash-lite`) for classification. That free-text field is not sanitized of personal information by anything upstream — per the DB schema (`docs/CONTRACTS.md`), `text` is 10–2000 characters of free-form citizen input, and `location` and `reporter_contact` are separate fields that may or may not also be embedded in the free text itself. Realistically, citizens will write things like "burst main flooding Ahmed's shop on Street 12, call 0300-xxxxxxx" directly into the complaint body — names, addresses, and phone numbers routinely end up inside the very text that gets sent for triage.

**What we verified about Gemini's free tier** (`docs/OPEN-DECISIONS.md` #1, checked 2026-09-19 directly against `ai.google.dev/gemini-api/docs/pricing`): the free tier we're using is confirmed to let Google use submitted inputs to improve its models. This is not a hypothetical caveat — it's the specific tier this project is built on, because the free tier is what makes the assignment's zero-cost requirement work at all.

**What actually leaves the machine, today, with no mitigation:** the full complaint `text` field, verbatim, plus the `location` field, sent over HTTPS to Gemini's API for every complaint that goes through `LLMTriage` (i.e., every complaint, unless `TRIAGE_PROVIDER` is set to `ollama` or `rules`). `reporter_contact` is not currently sent (it isn't part of the `TriageProvider.triage(text, location)` call signature per `docs/CONTRACTS.md`), but PII embedded inside the free-text `text` field itself is sent regardless, because nothing currently distinguishes "the complaint" from "PII incidentally written inside the complaint."

## Options

### Option A — Redact PII from complaint text before it reaches Gemini

Run a PII-detection/redaction pass (e.g. regex for phone-number patterns, a small NER pass, or a simple named-entity blocklist approach) over `text` before it's sent to `LLMTriage`, replacing detected names/phone numbers/addresses with placeholders, and send the redacted version.

- **Pros:** directly reduces what leaves the machine; the most defensible answer at viva if asked "what did you do about this"; aligns with data-minimization as a stated principle, not just a documented risk.
- **Cons:** redaction is never perfect — regex-based phone/address detection has real false-negative rates, especially for addresses and for names that don't follow a recognizable pattern (e.g. "Ahmed's shop" — is "Ahmed" flagged?). A false sense of security is arguably worse than an honestly-documented exposure, if the redaction is assumed complete and isn't. Also adds a real preprocessing step with its own failure modes (over-redaction could damage classification quality — "call 0300-xxx" being stripped might remove context the model needs to judge urgency, e.g. a phone number pattern near "please call before entering, gas leak" carrying no classification-relevant signal but a street name plausibly does).

### Option B — Send only a scrubbed excerpt, not the full complaint body

Send a bounded, lightly-processed version of the text (e.g. truncated, or with obvious contact-info patterns like phone numbers stripped, but without attempting full PII redaction) — narrower than Option A's ambition, framed as "reasonable effort" rather than "PII-safe."

- **Pros:** cheaper to implement and reason about than full redaction (e.g. a phone-number regex alone catches the most common case); doesn't claim more safety than it delivers.
- **Cons:** still sends names and addresses embedded in free text, since only phone-number-shaped patterns are targeted; the "we tried" middle ground may be the hardest position to defend at viva, since it invites "why didn't you go further" without the full protection of Option A.

### Option C — Accept and explicitly document the exposure

Send the complaint text to Gemini unmodified, and write plainly in this ADR (once decided) that PII in citizen-submitted text is sent to a third party whose free tier may use it for model improvement, why that's considered acceptable for this project's context (e.g.: this is a course assignment using synthetic/seeded demo data, not a real production deployment handling real citizens' real complaints; the seed data (`docs/CONTRACTS.md`, ≥30 realistic complaints) is fabricated, not real personal data), and what would need to change before this system could handle real complaints (e.g.: move to a paid tier with a no-training data agreement, or implement Option A properly, before any real deployment).

- **Pros:** simplest to implement — zero preprocessing code, zero risk of redaction bugs or classification-quality regressions; honest rather than falsely reassuring; the spec explicitly allows this stance ("accept and document the exposure" is one of its own three named options, §2.5).
- **Cons:** weakest privacy posture of the three; only defensible because this is coursework against seeded/synthetic data — the ADR would need to say that caveat out loud, not bury it, and the justification stops being valid the moment real citizen data is involved.

## What this ADR does not do

It does not pick one of the above. `LLMTriage`'s implementation should not be started (beyond the interface/factory shape in ADR 0001) until this is resolved, since the choice changes what `LLMTriage` is allowed to do with its input before calling Gemini.
