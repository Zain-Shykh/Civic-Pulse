"""SimulatedTriage — deterministic fake for CI. Seeded, no network, configurable failure injection.

docs/CONTRACTS.md §2.5 lists this as one of the four TRIAGE_PROVIDER-selectable
implementations, and docs/CONTRACTS.md line 110 requires CI to pin it by name
("simulated") for deterministic test runs. `name` follows RuleBasedTriage's
bare-string precedent rather than the llm:<provider> pattern, which is
specific to hosted LLM providers — see docs/specs/phase-05a-deterministic-
triage.md's Plan section, Open Question 1.
"""

from itertools import cycle

from app.providers.triage.base import Category, Priority, TriageResult

_FIXTURES: tuple[TriageResult, ...] = (
    TriageResult(
        category=Category.WATER, priority=Priority.HIGH,
        summary="Simulated water complaint", confidence=0.9,
    ),
    TriageResult(
        category=Category.ELECTRICITY, priority=Priority.NORMAL,
        summary="Simulated electricity complaint", confidence=0.85,
    ),
    TriageResult(
        category=Category.SANITATION, priority=Priority.LOW,
        summary="Simulated sanitation complaint", confidence=0.8,
    ),
    TriageResult(
        category=Category.ROADS, priority=Priority.HIGH,
        summary="Simulated roads complaint", confidence=0.9,
    ),
    TriageResult(
        category=Category.STREETLIGHTS, priority=Priority.NORMAL,
        summary="Simulated streetlights complaint", confidence=0.85,
    ),
    TriageResult(
        category=Category.OTHER, priority=Priority.LOW,
        summary="Simulated other complaint", confidence=0.75,
    ),
)


class SimulatedTriage:
    name = "simulated"

    def __init__(self, always_raise: bool = False) -> None:
        self.always_raise = always_raise
        self._fixtures = cycle(_FIXTURES)

    def triage(self, text: str, location: str) -> TriageResult:
        if self.always_raise:
            raise RuntimeError("SimulatedTriage configured with always_raise=True")
        return next(self._fixtures)
