"""Selects a TriageProvider by the TRIAGE_PROVIDER env var. See ADR 0001.

An unrecognized value raises KeyError, which already satisfies ADR 0001's
"Consequences" requirement that a bad TRIAGE_PROVIDER value fail fast at
startup rather than on first request. See docs/specs/phase-05a-deterministic-
triage.md's Plan section, Open Question 3.

`_llm()` wires `LLMTriage` with its own `OllamaTriage` instance as its
fallback leg (Phase 16) — the production chain is `llm:gemini` ->
`llm:ollama` -> `rules:fallback`. `"ollama"` is also independently
selectable via TRIAGE_PROVIDER=ollama (docs/specs/phase-16-ollama-triage-
and-fallback-chain.md).
"""

import os
from collections.abc import Callable

from app.config import settings
from app.providers.triage.base import TriageProvider


def _rules() -> TriageProvider:
    from app.providers.triage.rules import RuleBasedTriage

    return RuleBasedTriage()


def _simulated() -> TriageProvider:
    from app.providers.triage.simulated import SimulatedTriage

    return SimulatedTriage()


def _ollama() -> TriageProvider:
    from app.providers.triage.ollama import OllamaTriage

    return OllamaTriage(base_url=settings.ollama_base_url)


def _llm() -> TriageProvider:
    from app.providers.triage.llm import LLMTriage
    from app.providers.triage.ollama import OllamaTriage

    if not settings.gemini_api_key.strip():
        raise RuntimeError(
            "TRIAGE_PROVIDER=llm requires a non-empty GEMINI_API_KEY; "
            "refusing to start rather than silently falling back to rules on every call."
        )
    return LLMTriage(
        api_key=settings.gemini_api_key,
        fallback=OllamaTriage(base_url=settings.ollama_base_url),
    )


_PROVIDERS: dict[str, Callable[[], TriageProvider]] = {
    "rules": _rules,
    "simulated": _simulated,
    "llm": _llm,
    "ollama": _ollama,
}


def get_triage_provider() -> TriageProvider:
    return _PROVIDERS[os.environ["TRIAGE_PROVIDER"]]()
