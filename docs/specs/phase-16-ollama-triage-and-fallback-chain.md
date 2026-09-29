# Phase 16: Real OllamaTriage — standalone provider + LLMTriage's automatic fallback rung
Status: not started
Depends on: Phase 5b (`LLMTriage`, `redaction.py`, the retry/fallback shape this mirrors), Phase 6 (`services/complaints.py`'s own fallback-and-observability wiring), Phase 7 (`GET /api/meta/providers` route)
Reads first: `docs/CONTRACTS.md` §2.5 (the `TriageProvider` interface, `triaged_by` pattern), `docs/architecture/ARCHITECTURE.md` (network segmentation, "backend is the only service that bridges edge/internal"), `docs/specs/phase-05b-llm-triage.md` (Open Question 1 — where this stub was deferred from), `backend/app/providers/triage/llm.py`, `backend/app/providers/triage/factory.py`, `backend/app/services/complaints.py`

## Goal
Replace `OllamaTriage`'s stub (`ollama.py`, currently `pass`) with a real, working `TriageProvider` implementation calling a local Ollama server, wired two ways: (1) directly selectable via `TRIAGE_PROVIDER=ollama`, and (2) automatically, as `LLMTriage`'s fallback leg before `RuleBasedTriage` — so the real chain in production is `llm:gemini` → `llm:ollama` → `rules:fallback`, matching `docs/CONTRACTS.md`'s own `triaged_by` pattern and the assignment's stated three-tier design intent. This closes `docs/RUBRIC-CHECKLIST.md` row 63 ("≥3 working implementations") to a genuine 4, and turns the `ollama_models` Compose volume from an honest "not wired up yet" placeholder into real, used infrastructure.

## Deliverables
- `backend/app/providers/triage/prompting.py` (new): the system-instruction text and the structured-output Pydantic schema (`category`/`priority`/`summary`/`confidence`), moved out of `llm.py` so `LLMTriage` and `OllamaTriage` share one definition instead of two independently-maintained near-copies. See Plan, "Shared engineering vs. duplication."
- `backend/app/providers/triage/llm.py`: import the shared pieces from `prompting.py` instead of defining them locally (mechanical, no behavior change); `LLMTriage.__init__` gains an optional `fallback: TriageProvider | None = None` parameter (defaults to `RuleBasedTriage()`, so every existing test that constructs `LLMTriage(api_key=...)` directly keeps working unchanged); the final fallback block (`llm.py:118-125`) stops hardcoding `triaged_by="rules:fallback"` and instead normalizes based on what the fallback provider actually reported — see Plan point 1.
- `backend/app/providers/triage/ollama.py`: real `OllamaTriage` implementation — `name = "llm:ollama"`, redacts via the existing `redaction.py`, calls a local Ollama server's `/api/chat` endpoint with `format: "json"`, validates the response against the shared schema, falls back to `RuleBasedTriage` (with the same tag-normalization logic as `LLMTriage`) on any failure.
- `backend/app/config.py`: `ollama_base_url: str = "http://ollama:11434"`.
- `backend/app/providers/triage/factory.py`: new `"ollama"` key in `_PROVIDERS`; `_llm()` now constructs `LLMTriage` with `fallback=OllamaTriage(...)` instead of relying on the class default.
- `backend/app/services/complaints.py`: `get_meta_providers`'s fallback flag (`services/complaints.py:153`) changes from a hardcoded `row["triaged_by"] == "rules:fallback"` string match to `row["triaged_by"] != provider.name` — see Plan point 1, "a second blind-relabel bug."
- `compose.yaml` / `compose.prod.yaml`: real `ollama` (long-running server, `internal`-only) and `ollama-pull` (one-shot puller, mirrors the existing `migrate` service pattern) services; `backend` depends on `ollama-pull: condition: service_completed_successfully`; `ollama_models`'s volume comment updated from "Ollama not wired up yet" to describe its real, now-active use.
- `docs/architecture/ARCHITECTURE.md` + `README.md`'s Mermaid diagram: the "backend is the only service that bridges edge and internal" claim gets corrected — `ollama-pull` also bridges both, for the one-shot model pull's egress need, and this is disclosed and justified, not silently left inconsistent.
- Tests (new/extended, see Plan's Verification section): `backend/tests/test_ollama_triage.py` (new), extensions to `backend/tests/test_llm_triage.py` (the wired fallback chain, including the tag-normalization fix), `backend/tests/test_triage_providers.py::TestFactory` (new `ollama` key + `_llm()`'s wiring), `backend/tests/test_routes_complaints.py::TestMetaAndStats` (the corrected fallback-flag definition).
- `docs/RUBRIC-CHECKLIST.md` row 63 — updated citation, at As-Built time only, once real verification exists.
- `docs/IMPLEMENTATION-PLAN.md`: new Phase 16 entry; Phase 15's stale "Unlocks: nothing further builds on this" corrected to point here.

## Non-goals
- Kubernetes manifests (`k8s/`) — no `ollama` Deployment/Service exists there today and nothing in the user's instructions for this phase mentions Kubernetes; adding it is out of scope here and would be undisclosed scope creep. Tracked as a gap, not silently closed.
- Any change to `TriageProvider.triage(text, location) -> TriageResult`'s method signature, or to `TriageResult`'s shape.
- A DB migration — `triaged_by` is an unconstrained `sa.String()` (confirmed by reading `backend/alembic/versions/be5a6b3416a1_create_complaints_table.py:70`), no `CHECK` constraint to update.
- Content-hash triage caching changes — `providers/cache.py`'s triage cache is already provider-agnostic (keyed on `text`+`location`, not on which provider answered); no change needed.
- A real, live-network integration test that pulls the real `qwen2.5:0.5b` model and calls a real running Ollama server inside CI — see Plan point 4. CI stays fully offline/deterministic; live verification is manual, pasted into the As-Built, same precedent as `LLMTriage`'s own live-Gemini verification.
- Redis-backed or otherwise shared retry/backoff logic between `LLMTriage` and `OllamaTriage` — Plan point 3 gives `OllamaTriage` no retry at all (single attempt), so there is no retry-loop code to share; only the prompt text and response schema are shared (Plan point 5).
- Any change to `docs/adr/0004-pii-and-data-governance.md`'s redaction scope — `OllamaTriage` reuses `redact()` verbatim, same redaction behavior and same disclosed residual risk as `LLMTriage`.

## Open Questions
None outstanding — the five investigation points named in the request are real, resolvable engineering questions, not ambiguities needing a human decision; each is resolved with cited evidence in the Plan below. Flag anything that turns out different once implementation starts, per `docs/WORKFLOW.md`'s standing "stop and ask" rule.

## Plan

**Files touched, in order:**
1. `backend/app/providers/triage/prompting.py` (new) — no dependency on anything else new.
2. `backend/app/providers/triage/llm.py` — import from `prompting.py`; `__init__` gains `fallback`; fallback-tag fix.
3. `backend/app/config.py` — `ollama_base_url`.
4. `backend/app/providers/triage/ollama.py` — real implementation.
5. `backend/app/providers/triage/factory.py` — `"ollama"` key; `_llm()` wires the real fallback.
6. `backend/app/services/complaints.py` — `get_meta_providers`'s fallback-flag fix.
7. `compose.yaml`, `compose.prod.yaml` — `ollama` + `ollama-pull` services, `backend`'s new `depends_on`.
8. `docs/architecture/ARCHITECTURE.md`, `README.md` — network-bridging claim correction.
9. Tests (per Deliverables' test list).
10. `docs/RUBRIC-CHECKLIST.md` row 63 + `docs/IMPLEMENTATION-PLAN.md` — last, at As-Built time.

### 1. The blind-relabel bug — and a second one found by inspection, not just the one named

**`llm.py:118-125` (named in the request):** today, `LLMTriage.triage()`'s final block unconditionally overwrites `triaged_by` to `"rules:fallback"` on whatever `self._fallback.triage(...)` returns. That's correct only because `self._fallback` is hardcoded to `RuleBasedTriage`, which only ever reports `triaged_by="rules"` — the override is really "relabel a plain rules result as a *fallback* rules result." Once `self._fallback` can be `OllamaTriage`, blindly overwriting would mislabel a genuine `llm:ollama` success as `rules:fallback`, hiding a real second-tier AI result from `GET /api/meta/providers`.

**Fix:** normalize instead of overwrite —
```python
fallback_result = await self._fallback.triage(text, location)
triaged_by = "rules:fallback" if fallback_result.triaged_by == "rules" else fallback_result.triaged_by
return TriageResult(
    category=fallback_result.category,
    priority=fallback_result.priority,
    summary=fallback_result.summary,
    confidence=fallback_result.confidence,
    triaged_by=triaged_by,
)
```
This preserves today's behavior exactly when the fallback is bare `RuleBasedTriage` (`"rules"` → `"rules:fallback"`, unchanged), correctly keeps `"llm:ollama"` when Ollama succeeds, and correctly keeps `"rules:fallback"` when Ollama's own internal fallback already produced that tag (below) — one conditional, not a special case per fallback type. `OllamaTriage.triage()`'s own fallback block uses the identical one-line ternary (duplicated, not shared — see point 5 for why).

**A second blind-relabel bug, found while reading the file the request named as "the observability surface at risk" (`services/complaints.py`), not asked for by name but the same class of bug:** `get_meta_providers` (`services/complaints.py:145-158`) computes each historical outcome's `"fallback"` flag as `row["triaged_by"] == "rules:fallback"` (line 153) — a hardcoded string match with the same blind spot as `llm.py`'s: it only recognizes the *last* rung of the chain as "a fallback happened." Once `llm:ollama` is a real, reachable outcome for a request whose *active* provider is `llm:gemini`, that outcome **is** a fallback event (Gemini failed) but the current check would report `fallback: false` for it — silently breaking exactly the dashboard signal `docs/RUNBOOK.md`'s "When triage starts failing" section already tells an operator to watch ("a rising share of fallback outcomes is the concrete signal that LLMTriage is failing"). **Fix:** `"fallback": row["triaged_by"] != provider.name` — a fallback is "the persisted outcome differs from the currently-active provider's own name," which is correct for every combination (`active=rules`→`"rules"` matches, never fallback; `active=llm:gemini`→ `"llm:ollama"` or `"rules:fallback"` both differ, both correctly `true`; `active=llm:ollama` (standalone) → `"llm:ollama"` matches (not fallback), `"rules:fallback"` differs (fallback, Ollama itself failed)). This has the same pre-existing caveat the current code already has and this doesn't newly introduce: a `TRIAGE_PROVIDER` config change retroactively reinterprets older rows' fallback status against the *new* active provider, since nothing persists "what was active at write time" — not a new problem, a generalization of one already accepted.

### 2. Model-pull vs. network segmentation — investigated, not guessed

Confirmed by direct research into the official `ollama/ollama` image (not assumed): its default `ENTRYPOINT`/`CMD` is `ollama serve` only — it does **not** support "pull a model on first serve" out of the box. The documented, real pattern for pre-pulling a model in Compose is a second, one-shot service that waits for the server's healthcheck, issues the pull against the running server, and exits — exactly the shape this repo already uses for `migrate` (`compose.yaml:40-53`).

**Design, mirroring `migrate`:**
```yaml
ollama:
  image: ollama/ollama:0.34.4   # real, current stable tag (Docker Hub, confirmed Sept 2026) — never :latest
  networks:
    - internal                  # never gets egress, same segmentation posture as postgres/redis
  volumes:
    - ollama_models:/root/.ollama
  healthcheck:
    test: ["CMD-SHELL", "ollama list || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 10
  restart: unless-stopped
  deploy:
    resources:
      limits:
        cpus: "2.0"
        memory: 2048M

ollama-pull:
  image: ollama/ollama:0.34.4
  networks:
    - edge      # egress, to reach registry.ollama.ai
    - internal  # to reach ollama:11434
  environment:
    OLLAMA_HOST: ollama:11434
  depends_on:
    ollama:
      condition: service_healthy
  entrypoint: ["ollama", "pull", "qwen2.5:0.5b"]
  restart: "no"
```
`OLLAMA_HOST` makes the `ollama` CLI act as a remote-control client against the long-running server rather than starting its own — the pulled blobs land in the `ollama` service's own `/root/.ollama` (the volume), not in `ollama-pull`'s ephemeral filesystem, so `ollama-pull` needs no volume of its own. `backend` adds `ollama-pull: condition: service_completed_successfully` to its `depends_on`, mirroring `migrate`'s gate exactly — the automatic Gemini→Ollama fallback rung, and `TRIAGE_PROVIDER=ollama` standalone, both need the model genuinely present before backend starts serving, not a race.

**Consequence, disclosed rather than left inconsistent:** this makes `ollama-pull` a *second* service that bridges `edge`/`internal`, alongside `backend` — `docs/architecture/ARCHITECTURE.md`'s "backend is the only service that bridges edge and internal" (line 37) becomes false and needs correcting, not smoothing over. The justification differs from `backend`'s (steady-state LLM egress) but is the same shape of trade-off already accepted for `backend`: `ollama-pull` is one-shot (`restart: "no"`), exits immediately once the pull completes, and never accepts inbound connections — it's a transient, narrowly-scoped egress need, not a standing route out for the internal network's real long-running members (`postgres`, `redis`, `ollama` itself all stay `internal`-only, unaffected).

**Quickstart cost, disclosed, not silently absorbed:** a fresh `docker compose up` now also pulls `qwen2.5:0.5b` (~397 MB) once, cached in `ollama_models` thereafter — comparable to the base-image pulls (`postgres:16-alpine`, `node:22-alpine`, etc.) a clean clone already pays regardless of `TRIAGE_PROVIDER`. The README's "no further editing... out of the box" promise is about configuration (no API key needed for the default `TRIAGE_PROVIDER=rules`), not download size, so this doesn't break that claim, but the RUNBOOK/README deliverable above states the added first-run pull plainly rather than leaving a reader to discover it.

### 3. Total request latency budget — decided and justified, not left implicit

Today's worst case, `LLMTriage` alone: two attempts at up to `_TIMEOUT_MS=10_000` each (`llm.py:25`), one jittered inter-attempt delay of 0.5–1.5s (`llm.py:26,69`) → **≈21.5s worst case** before falling back.

**Decision: `OllamaTriage` gets a single attempt, no retry, 5-second timeout** (`_TIMEOUT_SECONDS = 5.0`, enforced via `httpx.AsyncClient(timeout=...)`) — chosen, not defaulted to Gemini's shape, because: (a) it is already the *second* hop of a chain that has already spent up to ~21.5s finding out the primary tier is unavailable — compounding a second full retry-with-jitter policy on top risks pushing total worst-case latency well past what's defensible for a synchronous citizen-facing request; (b) a local process either answers or is genuinely down/overloaded within a short, bounded window — retrying a crashed or saturated local service inside the same request rarely helps the way retrying a rate-limited *remote* API does (Gemini's retry targets are 429/5xx, transient-by-design failure modes; a local Ollama failure is more often "not running" or "out of memory," neither fixed by an immediate retry). **New worst case, stated plainly: ≈21.5s (Gemini) + 5s (Ollama) ≈ 26.5s** before dropping to the always-available `RuleBasedTriage` — a disclosed, bounded ~23% increase over today, not an open-ended one. `qwen2.5:0.5b` classifying a single short paragraph on CPU is expected to complete in low single-digit seconds in the common case (the whole reason the assignment's suggested 1B was downsized to 0.5B); 5s is headroom over that expectation, not a tight bound picked to look good on paper — confirmed empirically in Implementation/As-Built, not assumed here.

### 4. CI strategy — same precedent `LLMTriage` already set

`ci.yml`/`cd.yml` both pin `TRIAGE_PROVIDER=simulated` (`ci.yml:29`) — neither `LLMTriage` nor (now) `OllamaTriage` is ever constructed by the `test-backend` job at all; CI's determinism doesn't depend on either provider's real network behavior. Pulling a real ~397 MB model in CI for every run would be slow and add a real-network dependency (`registry.ollama.ai` reachability) to a job that today has none — not required by anything in `docs/CONTRACTS.md` or the assignment text, and the exact class of cost `docs/specs/phase-05b-llm-triage.md`'s own Deliverable #5 already declined for `LLMTriage` ("provider-level tests against a fake/mocked... transport, no live API calls"). **Decision: `OllamaTriage` gets the identical treatment** — `httpx.MockTransport` (a real, first-party `httpx` test utility already available via the existing `httpx==0.28.1` dev dependency, no new package) stands in for the Ollama HTTP server in `test_ollama_triage.py`, covering a valid structured response, a malformed/non-schema response, a timeout, and a connection failure — no real model pull, no real network, in CI. A real, live end-to-end run (`docker compose up`, real `qwen2.5:0.5b` pull, a real complaint through `TRIAGE_PROVIDER=ollama` and through the wired Gemini→Ollama fallback) is manual verification, pasted into the As-Built — the same precedent `LLMTriage`'s own live-Gemini check already set.

### 5. Shared engineering vs. duplication — recommended, and why

**Shared (`prompting.py`):** the system-instruction text (`llm.py`'s current `_SYSTEM_INSTRUCTION`) and the structured-output Pydantic schema (`_LLMResponseSchema`'s four fields) move to a new, small, dedicated module both providers import. Justification: these two pieces must be *identical* across providers for the mandatory prompt-injection guardrail test and the "structured output, enforced" requirement to mean the same thing regardless of which provider answered — two independently-maintained copies is a real, if slow, drift risk (someone tightens the schema or reworks the instruction wording for one provider during a later phase and forgets the other exists). This is not a new abstraction invented for its own sake — it's the same four fields and same instruction text that already exist once in `llm.py` today, relocated to where both real callers can reach them without one importing the other's "private" module.

**Not shared, deliberately:** a generic retry/timeout executor. Considered and rejected — `OllamaTriage` has no retry loop at all (point 3), so there is no meaningfully duplicated *retry* logic to extract; `LLMTriage`'s retry loop stays exactly as it is today, untouched. The one-line fallback-tag-normalization ternary (point 1) is duplicated verbatim in both `llm.py` and `ollama.py` rather than imported from a shared function — at one line, importing a function for it would cost more (an extra import, an extra indirection to read) than it saves, and the risk of the two copies silently diverging is low enough at that size to catch on inspection; this is a real one-line-rule judgment call, not an oversight.

## Verification required
- `cd backend && ruff check app/ tests/ && mypy app/` — no new lint/type errors.
- `cd backend && TRIAGE_PROVIDER=simulated pytest --cov=app --cov-report=term-missing --cov-fail-under=65` against real throwaway `postgres:16-alpine`/`redis:7-alpine` containers (same pattern as Phases 14/15) — full suite green, coverage ≥65%, real pasted output.
- `cd backend && pytest tests/test_ollama_triage.py tests/test_llm_triage.py tests/test_triage_providers.py tests/test_routes_complaints.py -v` — real pasted output covering: standalone `OllamaTriage` success/malformed/timeout/connect-failure paths; the mandatory injection-guardrail test reused for `OllamaTriage`; the factory's new `"ollama"` key and `_llm()`'s real fallback wiring; the wired `llm:gemini`→`llm:ollama` success path (proving the point-1 fix, not just "some fallback happened"); the wired `llm:gemini`→`llm:ollama` failure→`rules:fallback` path; the corrected `get_meta_providers` fallback-flag test.
- A live end-to-end check against the real compose stack: `docker compose up -d --build`, confirm `ollama-pull` exits `0` and `docker compose logs ollama-pull` shows a real completed pull, then a real complaint through each of `TRIAGE_PROVIDER=ollama` (standalone) and `TRIAGE_PROVIDER=llm` with Gemini deliberately made to fail (e.g. a temporarily invalid key) to force the real `llm:ollama` fallback path — real pasted `triaged_by` values and real measured latency, not asserted.
- `GET /api/meta/providers` hit live against the above, confirming the `fallback` flag is `true` for the `llm:ollama` outcome — the concrete regression check for the observability-surface bug named in point 1.

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md` or turns out underspecified once implementation actually starts — in particular, the real measured Ollama CPU latency turning out to make the 5-second budget (point 3) unrealistic, or the pinned `ollama/ollama:0.34.4` tag or `qwen2.5:0.5b` model tag turning out unavailable/renamed by the time this runs — stop and ask rather than silently adjusting and moving on.
