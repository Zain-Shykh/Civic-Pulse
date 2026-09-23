"""RuleBasedTriage — deterministic keyword fallback. Always available, never fails.

Category order and keyword/priority-signal tables are exactly the ones proposed
and validated (as a fixture-consistency check against backend/app/scripts/
seed.py's synthetic labels, NOT an accuracy measurement) in
docs/specs/phase-05a-deterministic-triage.md's Plan section. See that file
for the reasoning and the documented list of rows this table disagrees with
the fixture labels on.
"""

from app.providers.triage.base import Category, Priority, TriageResult

_CATEGORY_RULES: tuple[tuple[Category, tuple[str, ...]], ...] = (
    (Category.STREETLIGHTS, ("streetlight", "street light", "street lamp")),
    (
        Category.SANITATION,
        ("sewerage", "sewage", "garbage", "trash", "manhole", "drain", "toilet", "dead animal"),
    ),
    (Category.ROADS, ("road", "pothole", "speed breaker", "footpath", "debris")),
    (
        Category.ELECTRICITY,
        (
            "electricity", "voltage", "transformer", "meter", "wapda", "cable",
            "wiring", "lineman", "power",
        ),
    ),
    (Category.WATER, ("water", "pipeline", "tanker")),
)

_HIGH_PRIORITY_SIGNALS: tuple[str, ...] = (
    "urgent", "urgently", "danger", "dangerous", "risk", "risky", "unsafe", "hazard",
    "accident", "accidents", "exposed", "leaning", "contaminated", "unhygienic",
    "bitten", "flooding", "overflow", "faulty", "as soon as possible",
    "falls on someone", "school", "students", "smells bad", "bad smell",
)
_LOW_PRIORITY_SIGNALS: tuple[str, ...] = (
    "bill", "billing", "dispute", "delayed", "not coming on time", "flickering",
    "faded", "interfering", "wasting electricity",
)

_MATCH_CONFIDENCE = 0.7
_DEFAULT_CONFIDENCE = 0.35
_SUMMARY_LIMIT = 140


def _classify_category(lowered_text: str) -> tuple[Category, bool]:
    for category, keywords in _CATEGORY_RULES:
        if any(keyword in lowered_text for keyword in keywords):
            return category, True
    return Category.OTHER, False


def _classify_priority(lowered_text: str) -> Priority:
    if any(signal in lowered_text for signal in _HIGH_PRIORITY_SIGNALS):
        return Priority.HIGH
    if any(signal in lowered_text for signal in _LOW_PRIORITY_SIGNALS):
        return Priority.LOW
    return Priority.NORMAL


def _summarize(text: str) -> str:
    # Deterministic, not the AI-generated summary an LLM provider would give —
    # this provider has no model to ask, so the summary is the complaint text
    # itself, collapsed and truncated to fit TriageResult's 140-char limit.
    collapsed = " ".join(text.split())
    if len(collapsed) <= _SUMMARY_LIMIT:
        return collapsed
    return collapsed[: _SUMMARY_LIMIT - 3].rstrip() + "..."


class RuleBasedTriage:
    name = "rules"

    async def triage(self, text: str, location: str) -> TriageResult:
        lowered = text.lower()
        category, matched = _classify_category(lowered)
        priority = _classify_priority(lowered)
        return TriageResult(
            category=category,
            priority=priority,
            summary=_summarize(text),
            confidence=_MATCH_CONFIDENCE if matched else _DEFAULT_CONFIDENCE,
            triaged_by="rules",
        )
