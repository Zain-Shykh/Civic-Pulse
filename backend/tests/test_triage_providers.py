"""Unit tests for the deterministic triage providers — no HTTP, no DB.

The seed-data checks in TestRuleBasedTriageAgainstSeedFixtures are a
regression/consistency check, NOT an accuracy test: backend/app/scripts/
seed.py's category/priority values are synthetic fixture labels invented by
hand in Phase 3, not independently verified ground truth. See
docs/specs/phase-05a-deterministic-triage.md's Plan section for the full
reasoning and the pre-committed list of rows RuleBasedTriage is expected to
disagree with those fixture labels on.
"""

import pytest

from app.providers.triage.base import Category, Priority, TriageResult
from app.providers.triage.factory import get_triage_provider
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage
from app.scripts.seed import _COMPLAINTS

# Rows the Plan documents RuleBasedTriage as disagreeing with the fixture
# label on — asserted explicitly below so a change in behaviour is a visible
# test failure, not a silent gain or loss of agreement.
_KNOWN_CATEGORY_DISAGREEMENTS = {
    "Water line got mixed with sewerage line",
    "Illegal encroachment on footpath by shopkeepers",
    "Public park is being used as garbage dumping point",
    "Mobile tower signal is interfering with our TV cable connection",
}
_KNOWN_PRIORITY_DISAGREEMENTS = {
    "Public toilet near the bus stop is in very bad condition",
    "Public park is being used as garbage dumping point",
}


def _is_known(text: str, known_prefixes: set[str]) -> bool:
    return any(text.startswith(prefix) for prefix in known_prefixes)


class TestTriageResultShape:
    async def test_rule_based_triage_returns_valid_shape(self):
        result = await RuleBasedTriage().triage(
            "Water supply stopped since three days, please resolve.", "Karachi"
        )
        assert isinstance(result, TriageResult)
        assert isinstance(result.category, Category)
        assert isinstance(result.priority, Priority)
        assert len(result.summary) <= 140
        assert 0.0 <= result.confidence <= 1.0
        assert result.triaged_by == "rules"

    async def test_rule_based_triage_never_raises_on_no_keyword_match(self):
        result = await RuleBasedTriage().triage("asdf qwer zxcv nonsense input", "nowhere")
        assert result.category == Category.OTHER
        assert result.priority == Priority.NORMAL
        assert result.confidence < 0.7  # default-confidence branch

    async def test_rule_based_triage_summary_respects_length_limit(self):
        long_text = "word " * 200
        result = await RuleBasedTriage().triage(long_text, "somewhere")
        assert len(result.summary) <= 140

    async def test_simulated_triage_returns_valid_shape(self):
        result = await SimulatedTriage().triage("anything", "anywhere")
        assert isinstance(result, TriageResult)
        assert isinstance(result.category, Category)
        assert isinstance(result.priority, Priority)
        assert len(result.summary) <= 140
        assert 0.0 <= result.confidence <= 1.0
        assert result.triaged_by == "simulated"

    async def test_simulated_triage_cycles_deterministically(self):
        sequence_a = [await SimulatedTriage().triage("x", "y") for _ in range(6)]
        sequence_b = [await SimulatedTriage().triage("x", "y") for _ in range(6)]
        assert sequence_a == sequence_b

    async def test_simulated_triage_always_raise(self):
        provider = SimulatedTriage(always_raise=True)
        with pytest.raises(RuntimeError):
            await provider.triage("x", "y")

    async def test_simulated_triage_default_does_not_raise(self):
        provider = SimulatedTriage()
        await provider.triage("x", "y")  # must not raise


class TestFactory:
    def test_factory_resolves_rules(self, monkeypatch):
        monkeypatch.setenv("TRIAGE_PROVIDER", "rules")
        provider = get_triage_provider()
        assert isinstance(provider, RuleBasedTriage)
        assert provider.name == "rules"

    def test_factory_resolves_simulated(self, monkeypatch):
        monkeypatch.setenv("TRIAGE_PROVIDER", "simulated")
        provider = get_triage_provider()
        assert isinstance(provider, SimulatedTriage)
        assert provider.name == "simulated"

    def test_factory_fails_fast_on_unrecognized_value(self, monkeypatch):
        monkeypatch.setenv("TRIAGE_PROVIDER", "not-a-real-provider")
        with pytest.raises(KeyError):
            get_triage_provider()

    def test_factory_fails_fast_on_not_yet_implemented_ollama(self, monkeypatch):
        monkeypatch.setenv("TRIAGE_PROVIDER", "ollama")
        with pytest.raises(KeyError):
            get_triage_provider()


class TestRuleBasedTriageAgainstSeedFixtures:
    """Fixture consistency check, not an accuracy test — see module docstring."""

    @pytest.mark.parametrize("row", _COMPLAINTS, ids=lambda row: row[0][:40])
    async def test_category_consistency_with_seed_fixture(self, row):
        text, _location, _contact, expected_category = row[0], row[1], row[2], row[3]
        result = await RuleBasedTriage().triage(text, row[1])
        if _is_known(text, _KNOWN_CATEGORY_DISAGREEMENTS):
            assert result.category.value != expected_category, (
                "Documented disagreement now agrees with the fixture label — "
                "update the known-disagreements list and the Plan/As-Built."
            )
        else:
            assert result.category.value == expected_category

    @pytest.mark.parametrize("row", _COMPLAINTS, ids=lambda row: row[0][:40])
    async def test_priority_consistency_with_seed_fixture(self, row):
        text, expected_priority = row[0], row[4]
        result = await RuleBasedTriage().triage(text, row[1])
        if _is_known(text, _KNOWN_PRIORITY_DISAGREEMENTS):
            assert result.priority.value != expected_priority, (
                "Documented disagreement now agrees with the fixture label — "
                "update the known-disagreements list and the Plan/As-Built."
            )
        else:
            assert result.priority.value == expected_priority
