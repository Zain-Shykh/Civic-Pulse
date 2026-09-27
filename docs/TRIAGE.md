# The AI triage layer

This is a consolidated explainer of how CivicPulse triages a complaint — what the interface is, which implementations exist, how one gets selected, and what happens when the network-calling one fails. It cross-references the authoritative sources rather than restating them: `docs/adr/0001-provider-interface.md` (why this shape), `docs/adr/0004-pii-and-data-governance.md` (what leaves the machine and why), and the real files under `backend/app/providers/triage/`. If this document and one of those ever disagree, the ADR or the code wins — this file is a map, not a second source of truth.

## The interface

`backend/app/providers/triage/base.py:36-39` defines the contract every provider satisfies:

```python
class TriageProvider(Protocol):
    name: str
    async def triage(self, text: str, location: str) -> TriageResult: ...
```

`TriageResult` (`base.py:28-33`) is `category` / `priority` / `summary` (≤140 chars) / `confidence` (0.0–1.0) / `triaged_by`. `Category` (`base.py:13-19`) is one of `water, electricity, sanitation, roads, streetlights, other`; `Priority` (`base.py:22-25`) is `high, normal, low`.

`services/` (and everything above it) depends only on this Protocol — never on a concrete class — per the four-layer rule in `CLAUDE.md` and ADR 0001's Decision. Nothing outside `providers/triage/` knows or cares which implementation is live.

## Selection: `TRIAGE_PROVIDER` → factory

`backend/app/providers/triage/factory.py:41-49` is the one seam that knows how to construct each provider:

```python
_PROVIDERS: dict[str, Callable[[], TriageProvider]] = {
    "rules": _rules,
    "simulated": _simulated,
    "llm": _llm,
}

def get_triage_provider() -> TriageProvider:
    return _PROVIDERS[os.environ["TRIAGE_PROVIDER"]]()
```

An unrecognized `TRIAGE_PROVIDER` value raises `KeyError` at startup — fail fast, not a mysterious 500 on the first request (ADR 0001, Consequences). `_llm()` (`factory.py:30-38`) goes further: if `TRIAGE_PROVIDER=llm` but `GEMINI_API_KEY` is empty, it raises a `RuntimeError` naming exactly why, rather than starting and silently falling back to rules on every call — this is the application-level fail-fast `docs/specs/phase-11b-failfast-and-vpa-verification.md` added.

## The three real implementations

| Provider | File | `name` | What it does |
|---|---|---|---|
| `RuleBasedTriage` | `rules.py:71-84` | `"rules"` | Deterministic keyword match against fixed category/priority tables (`rules.py:13-39`). Never fails, never calls the network. Also the fallback target for `LLMTriage` below. |
| `SimulatedTriage` | `simulated.py:49-59` | `"simulated"` | Cycles through six fixed `TriageResult` fixtures (`simulated.py:15-46`), one per category. No randomness, no network — this is what makes CI deterministic (`ci.yml`/`cd.yml` both set `TRIAGE_PROVIDER: simulated`). |
| `LLMTriage` | `llm.py:72-125` | `"llm:gemini"` | Calls Gemini (`gemini-3.1-flash-lite`) for a real triage. The only provider with retry/fallback/redaction behaviour — see below. |

A fourth provider, `OllamaTriage` (`ollama.py`), is a stub only (`ollama.py:8`, literally `pass`) — intentionally unimplemented, tracked as an open question in `docs/specs/phase-05b-llm-triage.md` (Open Question 1), not silently dropped from the plan.

## `LLMTriage`: redaction, structured output, retry, fallback

Four things happen on every call to `LLMTriage.triage()` (`llm.py:82-125`), in order:

1. **Redaction** (`llm.py:83`, calling `redaction.py:30-42`) — `text` is run through `redact()` before it leaves the process. Phone numbers and email addresses are replaced with fixed placeholders (`[REDACTED-PHONE]`, `[REDACTED-EMAIL]`); `location` is sent unmodified. This is ADR 0004's Decision, implemented, not just documented — the ADR's stated residual risk (names, embedded addresses, unusually formatted numbers) is real and unfixed by design; see the ADR's Consequences section, not restated here.
2. **Structured output** — `GenerateContentConfig.response_schema` is set to `_LLMResponseSchema` (`llm.py:38-49`, `TriageResult` minus `triaged_by`), and the response is parsed with `model_validate_json` (`llm.py:97`) regardless of what Gemini actually returns. A `ValidationError` (malformed or safety-filtered output) is treated identically to any other failure — logged and routed straight to fallback (`llm.py:105-107`), no retry.
3. **Timeout + single jittered retry, retryable errors only** — `_is_retryable` (`llm.py:52-58`) allow-lists exactly `httpx.TimeoutException` and Gemini `APIError`s with code `429` or `5xx`; anything else (e.g. a `400`) is never retried. On a retryable failure, one retry happens after `_retry_delay_seconds` (`llm.py:61-69` — honours a real `Retry-After` header if Gemini sends one, otherwise a `0.5–1.5s` jittered sleep). The 10-second call timeout is set via `HttpOptions(timeout=_TIMEOUT_MS)` (`llm.py:25`, `78`).
4. **Fallback to `RuleBasedTriage`** — if both attempts fail, or the response fails schema validation, `LLMTriage` calls its own `self._fallback` (an instance of `RuleBasedTriage`, `llm.py:80`, `118`) and returns that result with `triaged_by` overwritten to `"rules:fallback"` (`llm.py:119-125`) — never `"llm:gemini"` on a call that never actually reached Gemini successfully.

`triaged_by` is therefore always one of `"rules"`, `"simulated"`, `"llm:gemini"`, or `"rules:fallback"` — the last one is the observable signal (`GET /api/meta/providers`, per `docs/CONTRACTS.md` §2.2) that a real triage call degraded to the deterministic fallback.

## Determinism in CI

CI never calls a live LLM. `TRIAGE_PROVIDER=simulated` (both `ci.yml` and `cd.yml`'s `test-backend` job) selects `SimulatedTriage`, whose fixed fixture cycle makes every test run reproduce the same sequence of results — the concrete answer to `docs/ENGINEERING-NOTES.md` Q4 ("what does 'correct' mean for a probabilistic component, and how did you keep CI deterministic").
