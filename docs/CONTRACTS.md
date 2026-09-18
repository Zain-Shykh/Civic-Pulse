# CivicPulse — Tested Contracts (verbatim extracts)

These are the pieces of the assignment that are *tested*, not merely described. Nothing here is paraphrased — each block is copied from the assignment text with its section number, so implementation can be checked against it directly and it can't silently drift as the project evolves. If an implementation needs to deviate from one of these, that's a decision to flag, not a refactor.

---

## API contract (§2.2)

| Method | Path | Behaviour |
|---|---|---|
| POST | /api/complaints | Validate → triage → persist. 201. 400 with a field-level error body. 429 when the caller exceeds the rate limit. |
| GET | /api/complaints/{id} | 200 / 404 |
| GET | /api/complaints | Filter by category, priority, status; paginate (page, page_size ≤ 100); return total. |
| PATCH | /api/complaints/{id}/status | Enforce the state machine. Invalid transition → 409 naming the attempted transition. |
| GET | /api/stats | Aggregates, Redis-cached, TTL 30 s, `X-Cache: HIT|MISS`. |
| GET | /api/meta/providers | Which triage provider is active, and the last 20 triage outcomes (provider, latency ms, fallback y/n). This is your observability surface. |
| GET | /health | Liveness. Process is alive. Must not touch the database. |
| GET | /ready | Readiness. 200 only if Postgres and Redis are both reachable; 503 naming the failed dependency. |
| GET | /metrics | Prometheus text format: request count, request latency histogram, triage latency, fallback counter. |

> Note: the rubric (§4, Category C) refers to "all ten endpoints to contract" but this table as written lists nine. Flagged in `docs/OPEN-DECISIONS.md` / ambiguity list — do not silently invent a tenth endpoint to make the count match.

Also from §2.2:

> /health and /ready are separate because Kubernetes uses them for different decisions: a failing liveness probe restarts your pod, a failing readiness probe removes it from the Service. Wire them backwards and a slow database becomes a restart loop across your entire deployment.

---

## Domain rules — status state machine (§2.2)

> Status state machine. open → in_progress → resolved; open → rejected; in_progress → rejected. resolved and rejected are terminal. Everything else is 409. Implement it as an explicit transition table, not a chain of ifs.

Valid transitions:
- `open → in_progress`
- `in_progress → resolved`
- `open → rejected`
- `in_progress → rejected`

Terminal states: `resolved`, `rejected`. Any transition not in the list above → `409`, naming the attempted transition (per the API contract row for `PATCH /api/complaints/{id}/status`).

---

## Database schema — minimum schema (§2.3)

| Column | Notes |
|---|---|
| id | UUID, server-generated |
| text | 10–2000 chars, enforced in the DB as well as the app |
| location | 3–200 chars |
| reporter_contact | nullable |
| category | enum: water · electricity · sanitation · roads · streetlights · other |
| priority | enum: high · normal · low |
| status | enum: open · in_progress · resolved · rejected, default open |
| ai_summary | nullable — one line, ≤ 140 chars |
| triaged_by | llm:groq · llm:ollama · rules · rules:fallback |
| triage_latency_ms | integer — you cannot reason about cost or latency without measuring it |
| created_at / updated_at | timestamptz, UTC |

Additional requirements from §2.3:

> Required: indexes on (status, priority) and created_at — and a sentence in your engineering notes on which query each one serves. An unexplained index is cargo cult.

> Required: an idempotent seed command loading ≥ 30 realistic complaints in Urdu-influenced English, spread across categories. Running it twice must not duplicate rows.

> Persistence contract. docker compose down then up must preserve every row. On Kubernetes, deleting the Postgres pod must preserve every row. You will demonstrate both.

> Schema managed by Alembic migrations — no CREATE TABLE in application startup code, ever.

---

## AI layer — TriageProvider interface / TriageResult schema (§2.5)

```python
class TriageResult(BaseModel):
    category: Category
    priority: Priority
    summary: str = Field(max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)

class TriageProvider(Protocol):
    name: str
    def triage(self, text: str, location: str) -> TriageResult: ...
```

Four implementations, selected by `TRIAGE_PROVIDER`:

| Provider | Use |
|---|---|
| LLMTriage | Production path. Calls a free-tier hosted model. |
| OllamaTriage | Fully offline path, a container in your Compose stack. Same interface. |
| RuleBasedTriage | Deterministic keyword fallback. Always available, never fails. |
| SimulatedTriage | Deterministic fake for CI — seeded, no network, configurable failure injection. |

The engineering requirements around every provider call (§2.5):

1. Structured output requested (JSON mode / tool calling / response schema), then **validated against the Pydantic model regardless** — the model will eventually return prose, a code fence, an out-of-enum category, or an oversized summary.
2. Hard timeout, 10 seconds, on every call.
3. Retry once, with jitter — only on timeout, 429, and 5xx. Never retry a 400.
4. Fall back to `RuleBasedTriage` on exhausted retries; record `triaged_by = "rules:fallback"`. A user must never see a 500 because a third party was rate-limited.
5. Cache by content hash in Redis, 24 h TTL — duplicate complaints cost one inference, not N. Measured hit rate must be reported.
6. Never log the API key. Environment / Kubernetes Secret / GitHub Secrets only, never a file in the repo.
7. Prompt-injection guardrail: treat complaint text as untrusted data, delimit it clearly, constrain output to the enum, reject anything outside it. One test must submit an injection attempt and assert the category is still schema-decided.

Mandatory test (§2.5, "Determinism"):

> Write this test if you write no other: given a provider that always raises, POST /api/complaints still returns 201 and triaged_by == "rules:fallback".

CI determinism requirement: CI is pinned to `SimulatedTriage`. No `time.sleep()` in tests, no re-running to get a pass.

---

## Redis — cache and rate-limiter behaviour (§2.4)

Redis 7 does two jobs, deliberately.

**Job 1 — read-through cache for `/api/stats`.**
> TTL 30 s. X-Cache: HIT|MISS. Invalidate on write, so a newly submitted complaint appears in the stats immediately rather than up to 30 seconds later. Be able to explain at viva why TTL and explicit invalidation, when either alone seems sufficient.

**Job 2 — distributed rate limiter.**
> A fixed-window or token-bucket counter in Redis, keyed by client IP, protecting POST /api/complaints. Exceeded → 429 with a Retry-After header.

> It must be distributed, in Redis, not an in-process dictionary, because the moment the HPA scales you to four pods an in-process limiter permits four times the traffic.

**Persistence.**
> Enable AOF on a named volume. Then answer, in your notes: why does the cache need a volume when the whole point of a cache is that it can be rebuilt?

**Related — triage result cache (§2.5, distinct from the stats cache above):** content-hash keyed, 24 h TTL, reduces duplicate-complaint inference cost. Same Redis instance, different key namespace/purpose — this is the "same infrastructure serving two [really three] purposes" point made in §1.3.
