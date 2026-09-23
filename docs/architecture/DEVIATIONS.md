# Deviations from the assignment's literal text

Running log of every place the implementation deliberately departs from the assignment's literal wording, with the justification for each — a paper trail for viva ("why does your code not match §X word-for-word"), not a place to record ambiguities that are still open (those live in `docs/OPEN-DECISIONS.md`). Only add an entry here once a deviation is actually decided and justified; append, don't rewrite history.

## 2026-09-19 — `triaged_by` value uses `llm:gemini`, not `llm:groq`

**Spec text (§2.3, via `docs/CONTRACTS.md`):** `triaged_by` column notes list values as `llm:groq · llm:ollama · rules · rules:fallback`.

**What we do instead:** `LLMTriage` records `triaged_by = "llm:gemini"`.

**Justification:** the listed values are a naming *pattern* — `llm:<provider>` — illustrated with Groq as the example hosted provider (Groq being the spec's own "recommended primary," §2.5), not a closed enum the database or tests are meant to validate literally against. The actual chosen provider is Gemini (`docs/OPEN-DECISIONS.md` #1), decided and verified separately. Recording `llm:groq` when the provider making the call is actually Gemini would be an outright false statement in the data — the `triaged_by` column exists specifically so `/api/meta/providers` (§2.2) can report "which triage provider is active" accurately; hardcoding the spec's example string regardless of actual provider would defeat that column's entire purpose. Substituting the real provider name into the documented pattern is the reading that keeps the column meaningful, not a shortcut around the spec.

**Where else this shows up:** `docs/CONTRACTS.md` (schema table note), `docs/adr/0001-provider-interface.md` (Resolved section), `docs/architecture/SCHEMA.md` (ERD note).
