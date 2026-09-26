"""Selects a TriageProvider by the TRIAGE_PROVIDER env var. See ADR 0001.

"ollama" is intentionally not wired yet — OllamaTriage's scope/phase is still
an open question (docs/specs/phase-05b-llm-triage.md, Open Question 1). An
unrecognized or not-yet-implemented value raises KeyError, which already
satisfies ADR 0001's "Consequences" requirement that a bad TRIAGE_PROVIDER
value fail fast at startup rather than on first request. See
docs/specs/phase-05a-deterministic-triage.md's Plan section, Open Question 3.
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


def _llm() -> TriageProvider:
    from app.providers.triage.llm import LLMTriage

    if not settings.gemini_api_key.strip():
        raise RuntimeError(
            "TRIAGE_PROVIDER=llm requires a non-empty GEMINI_API_KEY; "
            "refusing to start rather than silently falling back to rules on every call."
        )
    return LLMTriage(api_key=settings.gemini_api_key)


_PROVIDERS: dict[str, Callable[[], TriageProvider]] = {
    "rules": _rules,
    "simulated": _simulated,
    "llm": _llm,
}


def get_triage_provider() -> TriageProvider:
    return _PROVIDERS[os.environ["TRIAGE_PROVIDER"]]()
