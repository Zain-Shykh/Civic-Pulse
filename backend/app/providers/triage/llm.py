"""LLMTriage — calls Gemini (gemini-3.1-flash-lite) for production triage.

Will implement: PII redaction on `text` before the call (ADR 0004), a
10-second timeout, one jittered retry on timeout/429/5xx only, structured
output validated against TriageResult, and triaged_by = "llm:gemini" on
success (docs/architecture/DEVIATIONS.md). Stub only for this phase.
"""

pass
