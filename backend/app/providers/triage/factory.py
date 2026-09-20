"""Selects a TriageProvider by the TRIAGE_PROVIDER env var. See ADR 0001.

"llm"/"ollama" are intentionally not wired yet — those classes don't exist
until Phase 5b. An unrecognized or not-yet-implemented value raises KeyError,
which already satisfies ADR 0001's "Consequences" requirement that a bad
TRIAGE_PROVIDER value fail fast at startup rather than on first request. See
docs/specs/phase-05a-deterministic-triage.md's Plan section, Open Question 3.
"""

import os
from collections.abc import Callable

from app.providers.triage.base import TriageProvider


def _rules() -> TriageProvider:
    from app.providers.triage.rules import RuleBasedTriage

    return RuleBasedTriage()


def _simulated() -> TriageProvider:
    from app.providers.triage.simulated import SimulatedTriage

    return SimulatedTriage()


_PROVIDERS: dict[str, Callable[[], TriageProvider]] = {
    "rules": _rules,
    "simulated": _simulated,
}


def get_triage_provider() -> TriageProvider:
    return _PROVIDERS[os.environ["TRIAGE_PROVIDER"]]()
