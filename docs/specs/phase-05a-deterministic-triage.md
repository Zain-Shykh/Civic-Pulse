# Phase 5a: Deterministic triage providers
Status: not started
Depends on: Phase 2 (stub files, `TriageProvider` shape referenced in ADR 0001) — nothing from Phase 3 or 4 (`docs/IMPLEMENTATION-PLAN.md`, Phase 5: "Depends on: nothing from Phases 3–4 — this is the most self-contained slice")
Reads first: `docs/CONTRACTS.md` §2.5 (AI layer), `docs/adr/0001-provider-interface.md`, `docs/IMPLEMENTATION-PLAN.md` (Phase 5 section)

## Goal
Implement the two triage providers that need no network call and no API key — `RuleBasedTriage` and `SimulatedTriage` — plus the shared `TriageResult`/`TriageProvider` contract they both implement and the factory that selects between them by `TRIAGE_PROVIDER`, so CI can be wired to a fully deterministic provider before any Gemini integration exists (`docs/IMPLEMENTATION-PLAN.md`, Phase 5a: "Doing these first means CI can be wired up and made green immediately, rather than waiting on a working Gemini integration").

## Deliverables
Each line cites the source that justifies it. Nothing below is included without one.

1. `backend/app/providers/triage/base.py` — real `TriageResult(BaseModel)` and `TriageProvider(Protocol)` definitions, exactly as specified: `TriageResult{category: Category, priority: Priority, summary: str (≤140 chars), confidence: float (0.0–1.0)}`, `TriageProvider{name: str, triage(text, location) -> TriageResult}`.
   *Cite: `docs/CONTRACTS.md` §2.5, lines 76–85 (the literal code block).*

2. `backend/app/providers/triage/rules.py` — `RuleBasedTriage` implementing the Protocol: deterministic keyword-based classification, always returns a `TriageResult`, never raises.
   *Cite: `docs/CONTRACTS.md` §2.5 provider table, line 93: "Deterministic keyword fallback. Always available, never fails."; `docs/IMPLEMENTATION-PLAN.md` Phase 5a.*

3. `backend/app/providers/triage/simulated.py` — `SimulatedTriage` implementing the Protocol: deterministic (seeded), no network calls, configurable failure injection (so callers can exercise the fallback path without a real provider failing).
   *Cite: `docs/CONTRACTS.md` §2.5 provider table, line 94: "Deterministic fake for CI — seeded, no network, configurable failure injection."; `docs/CONTRACTS.md` line 110: "CI is pinned to `SimulatedTriage`."; `docs/IMPLEMENTATION-PLAN.md` Phase 5a.*

4. `backend/app/providers/triage/factory.py` — a `get_triage_provider()` function reading `TRIAGE_PROVIDER` and returning a concrete provider instance, with `"rules"` and `"simulated"` wired to the classes above. Construction stays lazy per-branch (import inside each branch, not at module top).
   *Cite: `docs/adr/0001-provider-interface.md`, "Decision" section (factory shape, one function, lazy per-branch construction) and "Consequences" (env var must fail fast on an unrecognized value at startup, not on first request).*
   *Note: `"llm"` and `"ollama"` are not wired yet — see Open Questions #3.*

5. `backend/tests/test_triage_providers.py` — unit tests instantiating `RuleBasedTriage` and `SimulatedTriage` directly (no HTTP, no DB), asserting on `TriageResult` field constraints (category/priority are valid enum members, summary ≤140 chars, confidence in range), and asserting the factory resolves `"rules"`/`"simulated"` to the right class.
   *Cite: `docs/IMPLEMENTATION-PLAN.md` Phase 5a, "Done looks like": "unit tests instantiate each provider directly (no HTTP, no DB) and assert on `TriageResult` shape."*

## Non-goals
- `LLMTriage` / `OllamaTriage` — Phase 5b (Gemini client, PII redaction, network I/O). Not this phase.
- The retry/timeout/fallback-to-`RuleBasedTriage` wrapper (`docs/CONTRACTS.md` §2.5 items 2–4) — per ADR 0001, "the retry/timeout/fallback/cache wrapper... wraps `LLMTriage` specifically... `RuleBasedTriage` is the fallback target, not a wrapped provider itself." That wrapper is 5b/Phase 6 work, not this phase's.
- PII redaction (ADR 0004) — applies to the LLM path only.
- Content-hash Redis caching of triage results (`docs/CONTRACTS.md` §2.5 item 5) — a concern for whichever provider makes a real network call; not exercised by either provider in this phase.
- Service-layer orchestration, routes, or the mandatory `POST /api/complaints` fallback test (`docs/CONTRACTS.md` line 106–108, "given a provider that always raises, `POST /api/complaints` still returns 201...") — that test needs the service layer and routes to exist (Phase 6/7); can't be written against bare providers.
- No edits to `llm.py` / `ollama.py` beyond their existing Phase 2 stub state.

## Open Questions
Flagged rather than silently decided, per instruction. Do not proceed on any of these without a decision.

1. **Does `simulated.py` have a legitimate purpose, or is it unspecified scope?**
   The file's current docstring (Phase 2 stub) reads: *"SimulatedTriage — deterministic fake for CI. Seeded, no network, configurable failure injection. TRIAGE_PROVIDER=simulated is what CI pins to (docs/CONTRACTS.md, 'Determinism, and how to test a system that is not')..."*
   It's true that `triaged_by`'s listed value pattern (`docs/CONTRACTS.md` line 55/69: `llm:groq · llm:ollama · rules · rules:fallback`) never mentions "simulated" — that part of the premise checks out.
   But `SimulatedTriage` itself is not unspecified: `docs/CONTRACTS.md` §2.5 lists it as one of the four required, `TRIAGE_PROVIDER`-selectable implementations (line 87: "Four implementations, selected by `TRIAGE_PROVIDER`"; line 94), `docs/CONTRACTS.md` line 110 requires CI to pin it by name, and ADR 0001's factory-shape example includes it as a fourth, equal entry in `_PROVIDERS` alongside llm/ollama/rules. So this is not "a test double never exposed as a production-selectable provider" — it IS a production-selectable provider (selectable via the same env var as the others, just typically only selected in CI/test config). **Recommendation: keep it, argue (b).** It's in scope for this phase per the Deliverables above.
   Two things this does leave genuinely open, which the "no simulated pattern in `triaged_by`" observation correctly surfaces:
   - What `triaged_by` value should `SimulatedTriage` itself record on its `TriageResult`-adjacent output? Nothing in `docs/CONTRACTS.md` or ADR 0001 specifies this. The most natural extension of the pattern would be `"simulated"`, but that's a naming choice with no citable source — flagging for the Plan step rather than deciding here.
   - The stub's docstring cites a section title, `"Determinism, and how to test a system that is not"`, that does not literally exist as a heading in `docs/CONTRACTS.md` — the real headings are `"Mandatory test (§2.5, "Determinism")"` (line 106) and a separate "CI determinism requirement" sentence (line 110). Minor inaccuracy in the stub's own prose; worth correcting when the real file is written, not a scope question.

2. **Should `RuleBasedTriage`'s actual keyword/pattern rules be specified in this Spec, or left as a Plan-stage decision?**
   `docs/CONTRACTS.md` specifies `RuleBasedTriage`'s behavioral contract only — deterministic, always available, never fails (line 93) — and the shared `TriageResult` shape it must produce. It does not specify which keywords map to which `category`/`priority`. There is no line to cite for a specific rule set, and per this spec's own citation rule, that means it can't be written in as a Deliverable requirement here.
   **My read: this belongs in the Plan, not the Spec.** It's a "how," not a "what" — TEMPLATE.md's own `## Plan` section exists precisely for "the key technical choices to be made and why," and a hardcoded keyword table is exactly that kind of choice (which keywords, which language(s), how ties/no-matches resolve to a default category/priority). Putting it in the Spec now would mean inventing a requirement with no source, which is the thing this spec is explicitly trying not to do.

3. **Self-flagged (same citation rule, applied to Deliverable #4):** `factory.py`'s handling of `"llm"` / `"ollama"` while those providers don't exist yet isn't specified anywhere — ADR 0001's example dict shows all four keys present, but that's the *end-state* shape, not a statement about the interim state while only two of four are implemented. Whether the factory should omit those keys entirely for now (so an unimplemented value is a plain `KeyError`) or include them mapped to something that fails fast with a clearer message is a Plan-stage call, not something I'm deciding here.

Note: `docs/specs/TEMPLATE.md` does not currently have an `## Open Questions` heading — I added it to this file only, per the instruction to add the heading if the template doesn't have one, and per "commit this file alone." If you want `## Open Questions` promoted into the template itself for all future specs, that's a separate, explicit edit to `TEMPLATE.md` — not done here.

## Plan
(Not started — mandatory before implementation per `docs/WORKFLOW.md`; drafted and committed as its own commit after this Spec is approved.)

## Verification required
- `python -m pytest backend/tests/test_triage_providers.py -v` — real pasted output, all tests passing.
- Manual confirmation that `TRIAGE_PROVIDER=simulated` and `TRIAGE_PROVIDER=rules` each resolve via `get_triage_provider()` to a working instance of the right class (paste the interactive/script output).
- Manual confirmation that an invalid `TRIAGE_PROVIDER` value fails fast with a clear error at startup, not on first request (paste the actual error/traceback).

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md` or `docs/adr/0001-provider-interface.md`, or is underspecified beyond what's already flagged under Open Questions above, stop and ask — do not silently resolve.

## As-Built
(Not started — filled in after the phase completes.)
