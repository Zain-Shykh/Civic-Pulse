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

Everything below marked **PROPOSAL** is exactly that — awaiting your approval, not a decision already made. Nothing in this section has been implemented.

### Files to be touched, in order

1. `backend/app/providers/triage/base.py` — `Category`/`Priority` enums, `TriageResult`, `TriageProvider`. Written first because every other file in this phase imports from it.
2. `backend/app/providers/triage/rules.py` — `RuleBasedTriage`, using the rule table proposed below.
3. `backend/app/providers/triage/simulated.py` — `SimulatedTriage`, using the `name`/failure-injection design proposed below.
4. `backend/app/providers/triage/factory.py` — `get_triage_provider()`, wiring `"rules"` and `"simulated"` per the proposal below.
5. `backend/tests/test_triage_providers.py` — unit tests against all of the above, no HTTP, no DB.

### Technical choice: where do `Category`/`Priority` live?

Nothing in the backend currently defines these as Python enums — the Alembic migration (`backend/alembic/versions/be5a6b3416a1_create_complaints_table.py`) defines them as Postgres enum types only, and the repository layer (Phase 4) reads/writes them as plain strings, never through a typed enum. `base.py` is the first consumer that needs them as Python types.

**PROPOSAL:** define `Category`/`Priority` as `str, Enum` classes directly in `base.py`, since it's the only current consumer. Not creating a separate shared `enums.py`/`models.py` module now — that would be building for a Phase 6/7 need that doesn't exist yet (repositories don't need it, and nothing else imports it today). If Phase 6 or 7 later needs the same enums, they import from `app.providers.triage.base`; if that import path turns out to be awkward once services/routes exist, relocating two small enum classes is a cheap refactor to revisit then, not a reason to build a shared module speculatively now.

### Technical choice: `RuleBasedTriage` confidence value

`TriageResult.confidence` is required (`docs/CONTRACTS.md` §2.5 code block) but nothing specifies what a keyword-matching provider should report. A real model's confidence and a keyword-hit aren't the same kind of number, but the field is mandatory on every `TriageResult`.

**PROPOSAL:** two fixed constants, not a computed score (there's nothing to genuinely compute a score from) — `0.7` when at least one category keyword matched, `0.35` when nothing matched and the complaint fell through to the `other`/`normal` default. This is a deliberate simplification with a known ceiling: a fixed number, not a real confidence estimate.

### Technical choice: `SimulatedTriage`'s failure-injection mechanism

`docs/CONTRACTS.md` says "configurable failure injection" but not how. The only concrete thing that needs to be exercisable, per `docs/CONTRACTS.md` line 106–108's mandatory test ("given a provider that always raises, `POST /api/complaints` still returns 201..."), is a provider that reliably raises on every call — that test belongs to Phase 6 (it needs the service layer), but `SimulatedTriage` needs to support the "always raises" mode now so Phase 6 can use it later without changes to this file.

**PROPOSAL:** `SimulatedTriage(always_raise: bool = False)`. Default behavior returns a deterministic (seeded, not random) `TriageResult` cycling through fixture outputs; `always_raise=True` makes every `.triage()` call raise, for exercising fallback paths. Not building a probabilistic fail-rate — nothing in `docs/CONTRACTS.md` or `docs/IMPLEMENTATION-PLAN.md` asks for one, and it would make tests non-deterministic, which directly contradicts why this provider exists.

### Proposed resolutions to the three Open Questions

**1. `SimulatedTriage`'s `triaged_by`/`name` value — PROPOSAL: `"simulated"`.**
`TriageResult` itself has no `triaged_by` field (see the code block in `docs/CONTRACTS.md` §2.5) — `triaged_by` is populated from `TriageProvider.name` by whatever calls the provider (the Service layer, Phase 6), except in the one documented override case: `docs/CONTRACTS.md` line 101 says the *fallback path specifically* records `triaged_by = "rules:fallback"` even though `RuleBasedTriage.name` is plain `"rules"` — that override belongs to the orchestration layer, not the provider. Given that, `RuleBasedTriage.name = "rules"` is the only precedent for a non-network provider, and it's a bare, unnamespaced string, not `rules:<something>`. Proposing `SimulatedTriage.name = "simulated"` for the same reason — bare, no `llm:`-style prefix (that prefix pattern is specific to hosted LLM providers per `docs/CONTRACTS.md` line 69 / ADR 0001's "Resolved: `triaged_by` naming" section, and `SimulatedTriage` isn't one).

**2. `RuleBasedTriage`'s keyword/pattern rules — PROPOSAL, full table below.**
Grounded in `backend/app/scripts/seed.py`'s 36 real seeded complaints (Phase 3 committed data — the closest thing to "example complaints" that actually exists in this repo, since the assignment text itself gives only one worked example, the burst-water-main sentence in its Motivation section) and in the category/priority enum definitions from `docs/CONTRACTS.md` §2.3 (lines 51–52). Category keywords were chosen by inspecting what words actually appear across each category's seeded examples; nearly every seeded complaint literally contains its own category name or a tight synonym, which is what the table below reflects.

*Category match — first match wins, checked in this order (most specific/least ambiguous first):*

| Order | Category | Keywords (case-insensitive substring match against `text`) |
|---|---|---|
| 1 | `streetlights` | `streetlight`, `street light`, `street lamp` |
| 2 | `sanitation` | `sewerage`, `sewage`, `garbage`, `trash`, `manhole`, `drain`, `toilet`, `dead animal` |
| 3 | `roads` | `road`, `pothole`, `speed breaker`, `footpath`, `debris` |
| 4 | `electricity` | `electricity`, `voltage`, `transformer`, `meter`, `wapda`, `cable`, `wiring`, `lineman`, `power` |
| 5 | `water` | `water`, `pipeline`, `tanker` |
| 6 | `other` | *(default — no match above)* |

`streetlights` is checked first specifically because seed complaints like "Streetlight pole is broken" would otherwise risk a false match against a looser `pole`/`light`-style electricity keyword.

*Priority match — checked independently of category, first match wins:*

| Order | Priority | Signal words |
|---|---|---|
| 1 | `high` | `urgent`, `urgently`, `danger`, `dangerous`, `risk`, `risky`, `unsafe`, `hazard`, `accident`, `accidents`, `exposed`, `leaning`, `contaminated`, `unhygienic`, `bitten`, `flooding`, `overflow`, `faulty`, `as soon as possible`, `falls on someone`, `school`, `students`, `smells bad`, `bad smell` |
| 2 | `low` | `bill`, `billing`, `dispute`, `delayed`, `not coming on time`, `flickering`, `faded`, `interfering`, `wasting electricity` |
| 3 | `normal` | *(default — neither above matched)* |

**This table was actually run against all 36 rows in `backend/app/scripts/seed.py`** (a throwaway verification script during Plan drafting, not a committed test — that's Deliverable #5, written during implementation). An earlier draft of this table was checked "by hand" and claimed to match every row; that claim was wrong — running it for real caught 5 category and 8 priority mismatches, which is exactly the kind of unverified claim `docs/WORKFLOW.md`'s audit step exists to catch. The table above already includes the fixes that were cheap and non-overfit (`lineman`/`power` for electricity; `overflow`, `faulty`, `as soon as possible`, `falls on someone`, `school`, `students`, `smells bad`/`bad smell` for `high`).

**What these numbers are, and what they are not:** the counts below are a *regression/consistency check* — do the keyword table's outputs agree with the `category`/`priority` values already sitting in `seed.py`? They are **not an accuracy measurement**. `seed.py`'s labels are synthetic fixture values invented by hand during Phase 3 seeding, not independently verified ground truth from any real municipal dataset or authoritative source — there is no "correct answer" here to be accurate against, only a self-consistency comparison against a label set I made up myself. Result after the fixes above:

- **Category: 32/36 agree with the fixture labels.** 4 rows disagree, all genuine internal disagreement between a lexical keyword match and the label I picked for that fixture row — not something more keywords fix without also breaking other rows:
  - *"Water line got mixed with sewerage line..."* → fixture says `water`, table says `sanitation` (contains both "water" and "sewerage"; ordering `sanitation` before `water` to protect the toilet/garbage rows below makes this one disagree).
  - *"Illegal encroachment on footpath by shopkeepers..."* → fixture says `other`, table says `roads` (mentions "footpath"/"road" but the fixture label treats it as encroachment, not road condition).
  - *"Public park is being used as garbage dumping point..."* → fixture says `other`, table says `sanitation` (mentions "garbage" but the fixture label treats it as park misuse).
  - *"Mobile tower signal is interfering with our TV cable connection..."* → fixture says `other`, table says `electricity` (mentions "cable" but the fixture label means TV cable, not electrical — internal disagreement with our own fixture labels, not an accuracy limitation).
- **Priority: 34/36 agree with the fixture labels.** 2 rows disagree, both labeled `low` in the fixture, table gives `normal` (no generic, non-overfit low-signal phrase found that doesn't also risk disagreeing with other rows): the public-toilet-condition complaint, and the same garbage-dumping-in-park complaint above.

None of these residual disagreements are being patched with narrower and narrower keyword phrases tuned to match one fixture row — that would be overfitting the rules to agree with labels I invented myself, not building a rule set that generalizes. This is also consistent with the spec: `docs/CONTRACTS.md` §2.5 requires `RuleBasedTriage` to be **deterministic and always available** — it says nothing about correctness, and there is no ground truth here for "correct" to mean anything against. Correctness against real-world category/priority judgment is precisely `LLMTriage`'s job, which is exactly why it exists as its own separate phase (5b) rather than being folded into the deterministic fallback (`docs/CONTRACTS.md` line 93 vs. the assignment's own framing in its Motivation section: "The information is in the text. Somebody has to read it."). `ponytail:` keyword-substring heuristic, self-consistency ceiling ~89–94% against our own fixture labels; upgrade path is `LLMTriage` (5b), not a bigger keyword table.
Deliverable #5's tests will assert against this documented consistency-check result (e.g. parametrized over the seed rows, asserting the known-disagreement rows explicitly rather than silently expecting full agreement) — not against a false full-agreement claim, and not framed as an accuracy test.

**3. `factory.py`'s handling of `"llm"`/`"ollama"` before those classes exist — PROPOSAL: omit the keys.**
Recommending **omit `"llm"`/`"ollama"` from `_PROVIDERS` entirely for now**, over wiring them to explicit `NotImplementedError` stubs. Reasoning: `docs/adr/0001-provider-interface.md`'s "Consequences" section already establishes the fail-fast requirement — "an unrecognized value should fail fast at startup" — and a `KeyError` on `_PROVIDERS[os.environ["TRIAGE_PROVIDER"]]` *is* a fail-fast-at-startup failure, just with a generic message. Adding `NotImplementedError` stubs for two providers whose classes don't exist yet means writing dead entries that Phase 5b will delete anyway (replacing the stub with a real lambda), which is exactly the kind of scaffolding-for-later `CLAUDE.md`'s workflow contract says not to add. If a clearer error message turns out to matter in practice once 5b starts, that's a one-line change to make at that point, not a reason to build it now.

## Verification required
- `python -m pytest backend/tests/test_triage_providers.py -v` — real pasted output, all tests passing.
- Manual confirmation that `TRIAGE_PROVIDER=simulated` and `TRIAGE_PROVIDER=rules` each resolve via `get_triage_provider()` to a working instance of the right class (paste the interactive/script output).
- Manual confirmation that an invalid `TRIAGE_PROVIDER` value fails fast with a clear error at startup, not on first request (paste the actual error/traceback).

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md` or `docs/adr/0001-provider-interface.md`, or is underspecified beyond what's already flagged under Open Questions above, stop and ask — do not silently resolve.

## As-Built
(Not started — filled in after the phase completes.)
