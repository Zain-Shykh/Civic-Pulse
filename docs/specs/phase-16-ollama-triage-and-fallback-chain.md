# Phase 16: Real OllamaTriage — standalone provider + LLMTriage's automatic fallback rung
Status: done. Implementation commit `bd8236b` on `dev`.
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
- `compose.yaml`: real `ollama` (long-running server, `internal`-only) and `ollama-pull` (one-shot puller) services, both behind `profiles: ["ollama"]` — inactive on a plain `docker compose up`, active via `docker compose --profile ollama up`. `backend` gets **no** `depends_on` relationship to either — see Plan point 2, revised after review. `ollama_models`'s volume comment updated from "Ollama not wired up yet" to describe its real, now-active use.
- `compose.prod.yaml`: the identical `ollama`/`ollama-pull` services, **without** `profiles:` (always active on a real deploy); `backend` still gets no `depends_on` on either, for the same reason as dev — see Plan point 2.
- `docs/RUNBOOK.md`: Deploy section gains a line documenting `docker compose --profile ollama up` for anyone locally exercising `TRIAGE_PROVIDER=ollama` or wanting to see the real Gemini→Ollama fallback — not left for a reader to discover by trial and error.
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

### 2. Model-pull vs. network segmentation — investigated, not guessed, **revised after review**

Confirmed by direct research into the official `ollama/ollama` image (not assumed): its default `ENTRYPOINT`/`CMD` is `ollama serve` only — it does **not** support "pull a model on first serve" out of the box. The documented, real pattern for pre-pulling a model in Compose is a second, one-shot service that waits for the server's healthcheck, issues the pull against the running server, and exits.

**Revision — the original draft below mirrored `migrate` too literally.** The first version of this Plan gave `backend` a hard `depends_on: ollama-pull: condition: service_completed_successfully`, reasoning it was the same shape as `migrate`'s gate. That's wrong, and was caught in review, not by me: `migrate` is unconditionally required for *any* request to work (there's no schema, no request succeeds). Ollama is optional-by-design — gated by `TRIAGE_PROVIDER`, and even when the chain uses it, it's a fallback rung behind Gemini, not the primary path. A hard startup gate on it is a real bug with two distinct, disclosed consequences, both confirmed against the real files rather than assumed:
- **CI:** `.github/workflows/ci.yml`'s `integration` job (lines 163-182) runs a real `docker compose -p civicpulse up -d --build` against this exact `compose.yaml`, with `TRIAGE_PROVIDER: rules` — a provider that never touches Ollama. A hard `depends_on` would make that job's `up -d --build` step (and therefore the whole job) depend on a real internet pull of `qwen2.5:0.5b` succeeding from a GitHub-hosted runner, for a test that has nothing to do with Ollama.
- **Local dev:** the README's default `TRIAGE_PROVIDER=rules` quickstart ("no further editing... out of the box") would now be gated on the same unrelated pull — a real regression risk against the "quickstart doesn't work from a clean clone" `-5` deduction on any machine with restricted network access to Ollama's registry.

**Corrected design, adopting both proposed fixes together, because they solve two different problems, not one problem two ways:**

1. **`backend` never gets a `depends_on` relationship to `ollama`/`ollama-pull`, in either Compose file.** If a request needing Ollama arrives before the model is pulled, `OllamaTriage`'s call fails exactly the way an unreachable Ollama fails once it's running normally (connection refused/timeout → fall back) — not a new failure mode, the existing one occurring earlier. This alone doesn't stop `ollama-pull` from still attempting a real network pull inside CI's `integration` job (Compose doesn't fail `up -d` just because a one-shot sibling service later exits non-zero, but the pull still runs and still costs real time/network for a job that doesn't need it) — hence point 2.

2. **`compose.yaml` (dev) gates `ollama` and `ollama-pull` behind `profiles: ["ollama"]`**, inactive on a plain `docker compose up`. This is *required*, not just tidier, for reason (1) to actually work: Compose auto-activates a dependency's profile to satisfy a `depends_on`, even when that profile wasn't requested (confirmed against Docker's own Compose profile documentation) — so as long as any service still `depends_on: ollama-pull`, the profile gate would be silently bypassed. Removing the `depends_on` (point 1) is what makes the profile gate in point 2 actually exclude these services from CI's and the default quickstart's plain `docker compose up`/`docker compose -p civicpulse up -d --build` — both invocations pass no `--profile` flag, so `ollama`/`ollama-pull` are never created, matching exactly the "rules mode never touches Ollama, so CI shouldn't pay for it" goal. Anyone locally exercising `TRIAGE_PROVIDER=ollama` or wanting to see the real Gemini→Ollama fallback needs `docker compose --profile ollama up` instead — documented in `docs/RUNBOOK.md`'s Deploy section (added to Deliverables below), not left for a reader to discover.

3. **`compose.prod.yaml` does *not* use profiles** — `ollama`/`ollama-pull` are unconditional there, matching the decision that the automatic cascade is live in production. Point 1 still applies in prod too, and for a related but distinct reason: gating a real production `backend` rollout on Ollama's pull would mean a slow/unreachable Ollama registry blocks deploys of the *primary* Gemini-backed path, for the sake of a secondary, best-effort fallback rung — a worse availability trade than the one being fixed for CI. Backend starts independently in prod as well; the fallback rung simply isn't ready yet if a request needs it before the pull finishes, same graceful-degradation path as everywhere else.

```yaml
# compose.yaml (dev) — gated
ollama:
  image: ollama/ollama:0.34.4   # real, current stable tag (Docker Hub, confirmed Sept 2026) — never :latest
  profiles: ["ollama"]
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
  profiles: ["ollama"]
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
`compose.prod.yaml` gets the identical two services, minus `profiles:` (always active there). `OLLAMA_HOST` makes the `ollama` CLI act as a remote-control client against the long-running server rather than starting its own — the pulled blobs land in the `ollama` service's own `/root/.ollama` (the volume), not in `ollama-pull`'s ephemeral filesystem, so `ollama-pull` needs no volume of its own. `backend` gains no new `depends_on` entry in either file (point 1, above).

**Consequence, disclosed rather than left inconsistent:** this still makes `ollama-pull` a *second* service that bridges `edge`/`internal`, alongside `backend` — `docs/architecture/ARCHITECTURE.md`'s "backend is the only service that bridges edge and internal" (line 37) becomes false and needs correcting, not smoothing over. The justification differs from `backend`'s (steady-state LLM egress) but is the same shape of trade-off already accepted for `backend`: `ollama-pull` is one-shot (`restart: "no"`), exits immediately once the pull completes, and never accepts inbound connections — it's a transient, narrowly-scoped egress need, not a standing route out for the internal network's real long-running members (`postgres`, `redis`, `ollama` itself all stay `internal`-only, unaffected).

**Quickstart cost — corrected by the profile fix above, not just disclosed:** the original draft accepted a ~397 MB first-run cost on every plain `docker compose up` as a reasonable trade. The profile gate removes that trade entirely for the default path — a plain `docker compose up` (`TRIAGE_PROVIDER=rules`, the README's documented default) starts exactly the same five services it does today, no Ollama pull, no size/time regression against the quickstart at all. The cost still exists, just moved to where it's actually opted into: `docker compose --profile ollama up` (documented in `docs/RUNBOOK.md`'s Deploy section, added to Deliverables) pulls `qwen2.5:0.5b` (~397 MB) once, cached in `ollama_models` thereafter, for anyone actually exercising `TRIAGE_PROVIDER=ollama` or the real Gemini→Ollama fallback locally. `compose.prod.yaml` (no profile gate) pays it unconditionally on a real deploy, which is the one place the assignment's own wording ("a container in your Compose file," `ollama_models` as a required, justified volume) expects it to be a standing cost, not an opt-in.

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
- **The regression check for point 2's fix:** `docker compose -p civicpulse up -d --build` with no `--profile` flag (i.e. exactly what `ci.yml`'s `integration` job runs) — real pasted `docker compose ps` output confirming `ollama`/`ollama-pull` were never created, and that `backend` reaches healthy without them. This is the concrete evidence that the CI cost/risk gap is actually closed, not just reasoned about.
- A live end-to-end check with the profile active: `docker compose --profile ollama up -d --build`, confirm `ollama-pull` exits `0` and `docker compose logs ollama-pull` shows a real completed pull, then a real complaint through each of `TRIAGE_PROVIDER=ollama` (standalone) and `TRIAGE_PROVIDER=llm` with Gemini deliberately made to fail (e.g. a temporarily invalid key) to force the real `llm:ollama` fallback path — real pasted `triaged_by` values and real measured latency, not asserted.
- `GET /api/meta/providers` hit live against the above, confirming the `fallback` flag is `true` for the `llm:ollama` outcome — the concrete regression check for the observability-surface bug named in point 1.

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md` or turns out underspecified once implementation actually starts — in particular, the real measured Ollama CPU latency turning out to make the 5-second budget (point 3) unrealistic, or the pinned `ollama/ollama:0.34.4` tag or `qwen2.5:0.5b` model tag turning out unavailable/renamed by the time this runs — stop and ask rather than silently adjusting and moving on.

## As-Built

Status: done. Implementation commit `bd8236b` on `dev`.

The Plan above (points 1, 3, 4, 5) held as approved. Point 2 changed materially during implementation — real facts turned up by actually pulling the image and actually running the pull that the Plan's own research pass didn't and couldn't have caught by reading documentation alone. Each is disclosed below, not smoothed over. Two additional bugs (a third blind-relabel instance, and an unrelated pre-existing gap) were also found live and fixed.

### Lint / type-check

```
$ ruff check app/ tests/
All checks passed!
$ mypy app/
Success: no issues found in 33 source files
```

### Full suite, real throwaway containers

```
$ docker run -d --name civicpulse-p16-pg -e POSTGRES_USER=civicpulse -e POSTGRES_PASSWORD=civicpulse -e POSTGRES_DB=civicpulse -p 55432:5432 postgres:16-alpine
$ docker run -d --name civicpulse-p16-redis -p 56379:6379 redis:7-alpine
$ alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> be5a6b3416a1, create complaints table
$ python -m app.scripts.seed
Seed complete: 36 new row(s) inserted, 0 already present.
$ TRIAGE_PROVIDER=simulated pytest --cov=app --cov-report=term-missing --cov-fail-under=65
...
app/providers/triage/factory.py        22      0   100%
app/providers/triage/llm.py            55      3    95%   36, 45-46
app/providers/triage/ollama.py         28      0   100%
app/providers/triage/prompting.py       8      0   100%
...
TOTAL                                 599     31    95%
Required test coverage of 65% reached. Total coverage: 94.82%
======================= 184 passed, 2 warnings in 6.36s ========================
```

184 = 183 pre-existing (post Phase 15) + 1 new (`test_used_fallback_true_for_a_non_rules_fallback_outcome`, the third bug fix below — the other new/extended test files net out to the same 183 total since `test_factory_fails_fast_on_not_yet_implemented_ollama` was replaced by `test_factory_resolves_ollama`, not added alongside it).

### The touched test files, verbose

```
$ pytest tests/test_ollama_triage.py tests/test_llm_triage.py tests/test_triage_providers.py tests/test_routes_complaints.py tests/test_services_complaints.py -v
...
tests/test_ollama_triage.py::TestSuccessPath::test_valid_structured_response_round_trips PASSED
tests/test_ollama_triage.py::TestMalformedResponse::test_out_of_schema_response_falls_back PASSED
tests/test_ollama_triage.py::TestConnectionFailures::test_timeout_falls_back_without_retry PASSED
tests/test_ollama_triage.py::TestConnectionFailures::test_connect_error_falls_back PASSED
tests/test_ollama_triage.py::TestConnectionFailures::test_server_error_falls_back PASSED
tests/test_ollama_triage.py::TestPromptInjectionGuardrail::test_injection_attempt_still_yields_schema_valid_category PASSED
tests/test_ollama_triage.py::TestRedaction::test_phone_and_email_redacted_before_outbound_request PASSED
tests/test_ollama_triage.py::TestFactoryResolvesOllama::test_factory_resolves_ollama PASSED
tests/test_ollama_triage.py::TestMandatoryDeterminism::test_provider_that_always_raises_falls_back_deterministically PASSED
tests/test_llm_triage.py::TestWiredFallbackChain::test_gemini_failure_falls_through_to_ollama_success PASSED
tests/test_llm_triage.py::TestWiredFallbackChain::test_gemini_and_ollama_both_fail_yields_rules_fallback PASSED
tests/test_triage_providers.py::TestFactory::test_factory_resolves_ollama PASSED
tests/test_triage_providers.py::TestFactory::test_factory_wires_ollama_as_llm_fallback PASSED
tests/test_routes_complaints.py::TestMetaAndStats::test_fallback_flag_is_outcome_differs_from_active_provider PASSED
tests/test_services_complaints.py::TestMandatoryDeterminism::test_used_fallback_true_for_a_non_rules_fallback_outcome PASSED
...
======================== 157 passed, 2 warnings in 2.23s =========================
```

(157 is these five files' own subtotal, not the full suite's 184 — every line shown above PASSED; only the wired-chain/fallback-flag-specific tests are excerpted here, the rest are the pre-existing per-provider unit tests carried over unchanged.)

### Real deviation 1: the official `ollama/ollama:0.34.4` image is ~9.3GB, not pulled-and-accepted — a custom image was built instead

Confirmed live, not assumed: `docker pull ollama/ollama:0.34.4` — **9.28GB disk, 3.75GB content**. This ran the test machine's disk from 94% to 99% full mid-pull and had to be aborted/cleaned up once, a real, disclosed operational cost the Plan's documentation-only research pass had no way to surface. Root cause, confirmed by downloading the real pinned `ollama-linux-amd64.tar.zst` release asset directly (not the Docker image): **1.4GB compressed → 2.1GB extracted**, of which `lib/ollama/cuda_v12` (1.2GB) + `cuda_v13` (812MB) + `vulkan` (41MB) = **~2.05GB** is GPU runner code, bundled unconditionally in the base Linux release tarball — the install script's GPU detection (`check_gpu`) only ever gates the *separate* ROCm (AMD) download, never CUDA, which ships in the base tarball regardless of host hardware. This design is deliberately CPU-only (`qwen2.5:0.5b`); none of that ~2GB is ever used.

**Decision, made with the user (not unilaterally):** build a custom, minimal, CPU-only image (`ollama/Dockerfile`) rather than pull the official one or use a third-party pre-built alternative — keeps `triaged_by="llm:ollama"` honest (still the real upstream binary) without a supply-chain dependency on an unofficial account. `debian:bookworm-slim` base (glibc, matching the official binary's own build), two-stage build (`fetch` downloads and strips `cuda_v12`/`cuda_v13`/`vulkan` in the same layer; `runtime` copies only `bin/ollama` + the stripped `lib/ollama` into the official manual-install's own `/usr` layout), non-root `ollama` user, pinned `OLLAMA_VERSION=0.34.4` build arg (confirmed the real latest release via GitHub's API, published 2026-09-23 — no newer tag exists to pin to instead). Real resulting image, confirmed by building it:

```
$ docker build -t civicpulse-ollama:dev ./ollama
...
$ docker images civicpulse-ollama:dev
IMAGE                   DISK USAGE   CONTENT SIZE
civicpulse-ollama:dev   211MB        55.4MB
```

**~44x smaller than the official image.** Two real bugs found and fixed while actually running it, neither guessable from documentation alone:
- The server defaults to binding `127.0.0.1` only — unreachable from any other container. Fixed with `ENV OLLAMA_HOST=0.0.0.0:11434` (the official image sets the same override for the same reason, confirmed after the fact).
- A Compose-mounted named volume at a path that doesn't already exist in the image gets created root-owned, unwritable by the non-root user. Fixed by pre-creating and `chown`-ing `/usr/share/ollama/.ollama` in the same `RUN` that creates the user, confirmed by a real volume-mount test (`ls -la` inside the running container showing `ollama:ollama` ownership from first boot).

**CI parity, decided with the user:** the new `civicpulse-ollama` image gets the identical treatment as `backend`/`frontend` — `ci.yml` builds and Trivy-scans it, `cd.yml` builds/pushes/SBOMs it to GHCR by commit SHA, `release.yml` re-tags it on a version tag. Real Trivy scan against the built image: **40 unique HIGH CVEs (0 CRITICAL)** — reported as 43 raw findings, since 3 of the 40 IDs are cross-attributed to two vendored packages each (e.g. one stdlib finding that `x/net` also vendors) — all inside the statically-linked binary's vendored Go stdlib/modules (`golang.org/x/crypto`, `x/net`, `x/mod`, `x/text`, `x/image`, `buger/jsonparser`), frozen at whatever versions upstream's own v0.34.4 build used — not reachable by any base-image or Dockerfile change on our side, and (confirmed) no newer upstream release exists to fix them. `ignore-unfixed: true` doesn't suppress them (fixed versions exist upstream, just not in a shipped ollama release yet). **Decided with the user:** a dated, scoped `ollama/.trivyignore` listing all 40 real CVE IDs, with the same class of justification `frontend/.trivyignore` already sets a precedent for (checked-today, no upgrade path, re-check later) — confirmed it actually suppresses everything:

```
$ trivy image --severity HIGH,CRITICAL --ignore-unfixed --ignorefile ollama/.trivyignore civicpulse-ollama:dev
civicpulse-ollama:dev (debian 12.15)   0 vulnerabilities
usr/bin/ollama                        0 vulnerabilities
```

### Real deviation 2: a real Docker/Go DNS bug, root-caused, changed `ollama-pull`'s network design entirely

The Plan's point 2 (as revised and approved) had `ollama-pull` join both `edge` and `internal`, talking to the real `ollama` service over `OLLAMA_HOST=ollama:11434`. Live-testing this against the real Compose stack, the pull failed consistently:

```
Error: pull model manifest: Get "https://registry.ollama.ai/v2/library/qwen2.5/manifests/0.5b": dial tcp: lookup registry.ollama.ai on 127.0.0.11:53: server misbehaving
```

Investigated rather than patched-around with a blind retry: `getent ahosts registry.ollama.ai` (glibc) succeeded 100% of the time in the exact same container/network; the real `ollama pull` (the binary's own Go DNS resolver) failed consistently in the exact same container/network. `GODEBUG=netdns=cgo` did **not** fix it (tried, verified it made no difference — a dead end, disclosed rather than left in as dead configuration). Isolated the real variable with throwaway networks: a container joining one `internal: true` network plus one plain bridge network reliably failed the same real `ollama pull`; the identical container/image/command joining two *plain* bridge networks (no `internal: true` at all) reliably succeeded, every time. This is a real Docker/Go interaction — the `internal: true` flag itself, not general dual-homing, not flakiness — confirmed by isolating it as the only variable across repeated trials.

**Fix:** redesigned `ollama-pull` to never need `internal` at all. `ollama/pull-model.sh` runs its own throwaway local `ollama serve` against the same shared `ollama_models` volume the real `ollama` service reads from, pulls the model directly into it, and exits — it never talks to the `ollama` service over the network. Confirmed end-to-end: a single-network (`edge`-only) puller wrote a real pulled model into a shared volume; a separately-started, `internal`-only `ollama` server, mounting the same volume, saw the model immediately with no restart:

```
$ docker exec real-ollama-server ollama list
NAME            ID              SIZE      MODIFIED
qwen2.5:0.5b    a8b0c5157701    397 MB    10 seconds ago
```

`ollama-pull` is now single-homed (`edge` only, no `depends_on` on `ollama` either — it never needed that service running, only the volume). This also reverts the Plan's earlier "`ollama-pull` also bridges edge/internal" disclosure in `ARCHITECTURE.md`/`README.md` — false again, in the good direction: `backend` really is the only service that bridges both networks, restored to its original wording.

### Real deviation 3: the shared prompt needed real enrichment for a 0.5B model

Live end-to-end testing (below) initially showed every standalone `TRIAGE_PROVIDER=ollama` request falling back to rules. The real cause: `qwen2.5:0.5b`'s bare `format: "json"` output under the original generic `SYSTEM_INSTRUCTION` ("classify into a category, priority, and one-line summary") consistently invented its own category ("emergency", not in the enum) and omitted `confidence` entirely — schema-invalid every time, confirmed by hitting the real running server directly and inspecting the raw response. Gemini never hit this because its `response_schema` parameter constrains generation structurally; Ollama's bare JSON mode only ever sees the prose. Fixed by enriching `prompting.py`'s shared `SYSTEM_INSTRUCTION` to explicitly name all four required keys and enumerate every valid `category`/`priority` value — confirmed against the real server, reliably schema-valid afterward (4/4 in a follow-up batch). Purely additive prompt content; harmlessly redundant for Gemini (which already gets the schema structurally), load-bearing for Ollama.

### Real deviation 4: a third blind-relabel bug, found live, not in the original two

While live-verifying the wired Gemini→Ollama fallback chain, `POST /api/complaints`'s own response reported `"used_fallback": false` for a request that had genuinely fallen back to `llm:ollama` — the exact same bug class as the Plan's point 1 (two instances), in a third location neither the request nor my own original review had caught: `services/complaints.py::submit_complaint`'s response dict hardcoded `"used_fallback": result.triaged_by == "rules:fallback"`. This field also drives the real `/metrics` `triage_fallback_total` Prometheus counter (`routes/complaints.py:52`), so the bug wasn't just a response-body cosmetic — it was silently undercounting a real observability metric. Fixed identically to the other two: `result.triaged_by != provider.name`. Confirmed against the real running stack, not just the new unit test:

```
$ curl ... # complaint whose active provider (llm:gemini) differs from its real outcome (llm:ollama)
{"triaged_by":"llm:ollama", ..., "used_fallback":true, ...}
$ curl http://backend:8000/metrics | grep triage_fallback
triage_fallback_total 1.0
```

### Real deviation 5: an unrelated, pre-existing gap found and fixed as a byproduct

Live-testing the Gemini→Ollama fallback required `TRIAGE_PROVIDER=llm` with a real (or deliberately invalid) `GEMINI_API_KEY` via `docker compose up`. This failed at container startup with `factory.py`'s own fail-fast `RuntimeError` — `compose.yaml`'s `backend` service never forwarded `GEMINI_API_KEY` to the container at all, a real, pre-existing gap unrelated to this phase (the README's own quickstart already promises "set `TRIAGE_PROVIDER=llm` and a real `GEMINI_API_KEY` in `.env`" — this was silently broken before Phase 16 touched anything). Fixed with a one-line addition (`GEMINI_API_KEY: ${GEMINI_API_KEY:-}`) so the promised behavior actually works; `compose.prod.yaml` already had this correctly (its `${VAR:?msg}` required-var syntax).

### Live end-to-end verification, full chain, real stack

**The regression check for point 2's fix — plain `docker compose up`, no profile:**

```
$ docker compose -p civicpulse up -d --build
$ docker compose -p civicpulse ps
NAME                    SERVICE    STATUS
civicpulse-backend-1    backend    Up (healthy)
civicpulse-frontend-1   frontend   Up (healthy)
civicpulse-postgres-1   postgres   Up (healthy)
civicpulse-redis-1      redis      Up (healthy)
```

Exactly the same five services as before Phase 16 — `ollama`/`ollama-pull` never created, no `--profile` flag passed. `POST /api/complaints` round-tripped correctly (`triaged_by: "rules"`).

**Live, with the profile active — real pull, real server, real classifications:**

```
$ TRIAGE_PROVIDER=ollama docker compose -p civicpulse --profile ollama up -d --build
$ docker wait civicpulse-ollama-pull-1
0
$ docker exec civicpulse-ollama-1 ollama list
NAME            ID              SIZE      MODIFIED
qwen2.5:0.5b    a8b0c5157701    397 MB    5 seconds ago
```

Standalone `TRIAGE_PROVIDER=ollama`, real complaints, after the prompt fix:

```
{"triaged_by":"llm:ollama","category":"water","priority":"normal", ...,"used_fallback":false, ...}   # 1.24s
{"triaged_by":"llm:ollama","category":"other","priority":"high", ..., "used_fallback":false, ...}    # 0.88s
```

Wired Gemini→Ollama fallback (`TRIAGE_PROVIDER=llm`, `GEMINI_API_KEY` deliberately invalid to force the real failure path):

```
$ curl -X POST http://localhost:8080/api/complaints -d '{"text":"...transformer sparking near the park entrance.", ...}'
{"triaged_by":"llm:ollama","category":"other","priority":"high",
 "ai_summary":"New complaint about a rare incident near the park entrance, suspected to be due to a transformer sparking.",
 "triage_latency_ms":1715,"used_fallback":true,"cache_hit":false}
```

(Corrected from an earlier draft of this As-Built, which had `used_fallback:false` here — a transcription error, not a code bug: `used_fallback` is `result.triaged_by != provider.name` (`services/complaints.py:110`), and `active_provider` for this run is `llm:gemini` while the outcome is `llm:ollama`, so it must be `true` — exactly what the `/api/meta/providers` block right below already showed for this same request. Caught and fixed during `docs/DEMO-VOICEOVER-SCRIPT.md`'s preparation, which needed this value to be internally consistent to cite it on camera.)

Real measured latency: **1.715s** (Gemini's fast-fail on an auth error + Ollama's real inference) — nowhere near the Plan's disclosed ≈26.5s worst case; that number was always a *worst*-case bound, not a typical one, and this confirms it wasn't understated.

`GET /api/meta/providers` against the same run, confirming point 1 and deviation 4's fixes together, live:

```
{"active_provider":"llm:gemini",
 "recent_outcomes":[
   {"provider":"llm:ollama","latency_ms":1715,"fallback":true},
   {"provider":"llm:ollama","latency_ms":669,"fallback":true},
   ...
 ]}
```

`fallback: true` correctly reported for every `llm:ollama` outcome while `active_provider` is `llm:gemini` — the exact regression check point 1 named as "the concrete evidence," now real, not asserted.

### Rubric / plan doc updates
- `docs/RUBRIC-CHECKLIST.md` row 63 — updated (see that file's own diff).
- `docs/IMPLEMENTATION-PLAN.md` — Phase 16 entry already added at Plan-commit time; no further change needed.
