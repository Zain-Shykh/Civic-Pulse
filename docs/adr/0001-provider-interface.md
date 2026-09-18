# ADR 0001: TriageProvider selection — env var + factory

## Status

Accepted

## Context

`docs/CONTRACTS.md` (§2.5) fixes the interface every triage implementation must satisfy:

```python
class TriageProvider(Protocol):
    name: str
    def triage(self, text: str, location: str) -> TriageResult: ...
```

Four implementations are required, selected by the `TRIAGE_PROVIDER` environment variable: `LLMTriage` (Gemini), `OllamaTriage`, `RuleBasedTriage`, `SimulatedTriage`. The rest of the system — routes, services — must not know or care which one is active; CI pins `SimulatedTriage` specifically so the test suite stays deterministic regardless of what runs in production.

## Decision

A single factory function in `backend/app/providers/triage/factory.py` reads `TRIAGE_PROVIDER` at process startup and returns one concrete `TriageProvider` instance. `services/` depends only on the `TriageProvider` Protocol, obtained once from the factory (e.g. via FastAPI dependency injection) — never on a concrete class name.

```python
# providers/triage/factory.py — shape, not final code
_PROVIDERS: dict[str, Callable[[], TriageProvider]] = {
    "llm": lambda: LLMTriage(...),
    "ollama": lambda: OllamaTriage(...),
    "rules": lambda: RuleBasedTriage(),
    "simulated": lambda: SimulatedTriage(...),
}

def get_triage_provider() -> TriageProvider:
    return _PROVIDERS[os.environ["TRIAGE_PROVIDER"]]()
```

Each provider is a standalone class in its own module (`llm.py`, `ollama.py`, `rules.py`, `simulated.py`), implementing the Protocol and nothing else — no shared base class is imposed beyond the Protocol itself, since Python's structural typing doesn't need one. The retry/timeout/fallback/cache wrapper described in `docs/CONTRACTS.md` wraps `LLMTriage` specifically (only the network-calling provider needs it); `RuleBasedTriage` is the fallback target, not a wrapped provider itself.

**Adding a fifth provider later** (e.g. a fine-tuned classifier, per §1.1's own "next year it's a fine-tuned classifier" framing) means: write one new class implementing the Protocol, add one entry to `_PROVIDERS`, done. No change to `services/`, `routes/`, or any existing provider file. This is the entire point of the interface — the reader must be replaceable without the system around it caring.

## Consequences

- The factory dict is the one place that knows every provider's construction details (env vars, base URLs, client instantiation) — a single seam, which is intentional, not accidental coupling.
- Provider construction should stay lazy per-branch (import inside each lambda/function, not at module top) so that, e.g., an `ollama` HTTP client isn't instantiated — and doesn't need to be reachable — when `TRIAGE_PROVIDER=simulated` in CI.
- `TRIAGE_PROVIDER` becomes a required, validated environment variable; an unrecognized value should fail fast at startup (not on the first request), so a typo'd config value surfaces immediately rather than as a mysterious 500 later.

## Alternatives considered

- **Plugin discovery (entry_points / auto-registration):** unnecessary indirection for a fixed, small set of known providers; would make it harder, not easier, to see at a glance what implementations exist.
- **A dependency-injection framework:** the assignment's own architecture already provides the seam (env var → factory); adding a DI library is complexity with no corresponding requirement.
- **An if/elif chain inside `services/`:** rejected outright — this is exactly the four-layer violation `CLAUDE.md` calls out: business-rule code would need to know provider construction details, and every future provider addition would mean editing `services/` instead of only adding a file.

## Resolved: `triaged_by` naming

`triaged_by` values (`docs/CONTRACTS.md` schema) are listed as `llm:groq · llm:ollama · rules · rules:fallback`. This is a naming **pattern** — `llm:<provider>` — illustrated with Groq as the example hosted provider, not a fixed, closed enum. `LLMTriage` records `triaged_by = "llm:gemini"`, following the pattern with the actual configured provider substituted in. This is a deliberate deviation from the spec's literal example value, logged in `docs/architecture/DEVIATIONS.md` for the viva paper trail.
