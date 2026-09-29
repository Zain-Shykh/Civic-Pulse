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

`backend/app/providers/triage/factory.py:55-64` is the one seam that knows how to construct each provider:

```python
_PROVIDERS: dict[str, Callable[[], TriageProvider]] = {
    "rules": _rules,
    "simulated": _simulated,
    "llm": _llm,
    "ollama": _ollama,
}

def get_triage_provider() -> TriageProvider:
    return _PROVIDERS[os.environ["TRIAGE_PROVIDER"]]()
```

An unrecognized `TRIAGE_PROVIDER` value raises `KeyError` at startup — fail fast, not a mysterious 500 on the first request (ADR 0001, Consequences). `_llm()` (`factory.py:40-52`) goes further: if `TRIAGE_PROVIDER=llm` but `GEMINI_API_KEY` is empty, it raises a `RuntimeError` naming exactly why, rather than starting and silently falling back to rules on every call — this is the application-level fail-fast `docs/specs/phase-11b-failfast-and-vpa-verification.md` added. `_llm()` also wires `LLMTriage` with its own `OllamaTriage` instance as its fallback leg (`factory.py:49-52`, Phase 16) — see "The fallback chain" below.

## The four real implementations

| Provider | File | `name` | What it does |
|---|---|---|---|
| `RuleBasedTriage` | `rules.py:71-84` | `"rules"` | Deterministic keyword match against fixed category/priority tables (`rules.py:13-39`). Never fails, never calls the network. Also the innermost fallback target for both `LLMTriage` and `OllamaTriage` below. |
| `SimulatedTriage` | `simulated.py:49-59` | `"simulated"` | Cycles through six fixed `TriageResult` fixtures (`simulated.py:15-46`), one per category. No randomness, no network — this is what makes CI deterministic (`ci.yml`/`cd.yml` both set `TRIAGE_PROVIDER: simulated`). |
| `LLMTriage` | `llm.py:50-113` | `"llm:gemini"` | Calls Gemini (`gemini-3.1-flash-lite`) for a real triage. On failure, falls through to `OllamaTriage` rather than straight to rules — see below. |
| `OllamaTriage` | `ollama.py:28-80` | `"llm:ollama"` | Real implementation, Phase 16 (`docs/specs/phase-16-ollama-triage-and-fallback-chain.md`) — no longer a stub. Calls a local Ollama server (`qwen2.5:0.5b`, a custom-built CPU-only image, `ollama/Dockerfile`) for a real, offline triage. Independently selectable via `TRIAGE_PROVIDER=ollama`, and also `LLMTriage`'s own fallback leg. |

## The fallback chain: `LLMTriage` → `OllamaTriage` → `RuleBasedTriage`

Both network-calling providers share the same shape: redact, call, parse, and on any failure hand off to `self._fallback` rather than raising. Chained together (the wiring `factory.py`'s `_llm()` does), a request against `TRIAGE_PROVIDER=llm` can pass through up to three rungs before returning:

1. **`LLMTriage.triage()`** (`llm.py:65-113`). Redacts `text` (`llm.py:66`, calling `redaction.py:30-42` — phone numbers and emails replaced with fixed placeholders per ADR 0004's Decision; `location` sent unmodified). Calls Gemini with `response_schema` set to `TriageResponseSchema` (`llm.py:67-70`), parsed with `model_validate_json` regardless of what Gemini actually returns (`llm.py:80`) — a `ValidationError` is treated as a failure, no retry (`llm.py:88-90`). Retryable transport/API errors (`_is_retryable`, `llm.py:30-36`: `httpx.TimeoutException`, or a Gemini `APIError` with code `429`/`5xx` — anything else, e.g. a `400`, is never retried) get exactly one retry after a jittered or `Retry-After`-driven delay (`llm.py:39-47`, `91-94`). The 10-second call timeout is set via `HttpOptions(timeout=_TIMEOUT_MS)` (`llm.py:26`, `61`).
2. **On failure, `OllamaTriage.triage()`** (`ollama.py:40-80`) — `LLMTriage`'s `self._fallback` (`factory.py:51`). Same redaction step (`ollama.py:41`). Single attempt, no retry, 5-second timeout (`ollama.py:25`, `37`) — a local process is either up or genuinely down, so retrying inside the same request rarely helps the way it does for a rate-limited remote API. On success, returns `triaged_by="llm:ollama"` (`ollama.py:63`).
3. **On failure, `RuleBasedTriage.triage()`** — `OllamaTriage`'s own `self._fallback` (`ollama.py:38`), the same deterministic keyword-match provider as above. Never fails.

**The tag is normalized, not overwritten** (`llm.py:101-106`, `ollama.py:68-73` — identical one-line ternary, duplicated by choice rather than shared, Phase 16 Plan point 5): `triaged_by = "rules:fallback" if fallback_result.triaged_by == "rules" else fallback_result.triaged_by`. This is what makes rung 2 observable at all — an earlier version of this logic unconditionally relabeled whatever the fallback returned as `"rules:fallback"`, which was only correct because the fallback used to always be `RuleBasedTriage` itself; once the fallback can be `OllamaTriage`, blindly overwriting would have hidden a real `llm:ollama` success behind a misleading `"rules:fallback"` tag. Fixed in Phase 16, along with the same class of bug in `services/complaints.py`'s `get_meta_providers` and `submit_complaint` (both compute `"fallback"`/`used_fallback` as `outcome != active_provider.name` rather than a hardcoded string match).

`triaged_by` is therefore always one of `"rules"`, `"simulated"`, `"llm:gemini"`, `"llm:ollama"`, or `"rules:fallback"` — everything except the first two rungs' own names (`"llm:gemini"`, `"llm:ollama"` when each is the *directly selected* provider, not a fallback outcome) is the observable signal (`GET /api/meta/providers`, per `docs/CONTRACTS.md` §2.2) that a real triage call degraded at least one rung from the actively configured provider.

## Determinism in CI

CI never calls a live LLM. `TRIAGE_PROVIDER=simulated` (both `ci.yml` and `cd.yml`'s `test-backend` job) selects `SimulatedTriage`, whose fixed fixture cycle makes every test run reproduce the same sequence of results — the concrete answer to `docs/ENGINEERING-NOTES.md` Q4 ("what does 'correct' mean for a probabilistic component, and how did you keep CI deterministic").
