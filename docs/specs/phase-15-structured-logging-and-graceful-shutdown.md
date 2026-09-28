# Phase 15: Structured logging + graceful shutdown
Status: not started
Depends on: Phase 7 (routes/main.py wiring — where cross-cutting middleware lives), Phase 6 (service-layer log calls this must propagate through), Phase 5b (LLMTriage/redaction log calls this must propagate through), Phase 11 (k8s `terminationGracePeriodSeconds: 30` + `preStop: sleep 5` already in `k8s/base/backend.yaml`, the environment row 38's SIGTERM behavior runs inside)
Reads first: `docs/RUBRIC-CHECKLIST.md` rows 37/38, `docs/CONTRACTS.md` (four-layer rule), `backend/app/main.py`, `backend/app/services/complaints.py`, `backend/app/providers/triage/llm.py`, `backend/app/providers/triage/redaction.py`

## Goal
Close two real, disclosed Category C gaps for real: (1) every log line emitted by the backend during a request's handling is a structured JSON object on stdout carrying a per-request `request_id`, including log calls that already exist today and are not being touched otherwise; (2) SIGTERM causes in-flight requests to finish and respond successfully before the process exits, verified by an actual subprocess-level test, not asserted from documentation or uvicorn's advertised defaults.

## Deliverables
- A new cross-cutting logging module (exact path/name decided in Plan) implementing: a JSON `logging.Formatter`, a per-request `request_id` (stdlib `contextvars`, not threaded through function signatures), and a `logging.Filter` that injects the current request's `request_id` into every `LogRecord` — so `backend/app/services/complaints.py`'s existing `logger.warning(...)`, `backend/app/providers/triage/llm.py`'s two `logger.warning`/`logger.info` calls, and `backend/app/providers/triage/redaction.py`'s two `logger.info` calls all carry `request_id` without editing their call sites.
- `backend/app/main.py`: wire in the request-id-generating ASGI middleware and the JSON logging configuration at startup.
- `backend/tests/test_logging.py` (or similar new file): real test(s) proving a request produces structured JSON log lines on stdout, that two log lines from the same request share one `request_id`, and that an existing call site (e.g. the rate-limiter or fallback warning) carries it without modification.
- `backend/tests/test_graceful_shutdown.py` (or similar new file): a real test that starts the app as an actual subprocess, sends a slow/in-flight request, sends the subprocess SIGTERM, and confirms the response completes successfully before the process exits.
- `backend/Dockerfile` CMD and/or `compose.yaml`'s backend `command:` override — touched only if the real SIGTERM test in Plan/Implementation shows uvicorn's default graceful-shutdown behavior is insufficient as-is; not touched if the default already works, and either way the finding is written up with real evidence, not assumed.
- `docs/RUBRIC-CHECKLIST.md` rows 37 and 38 flipped to `[x]` with real citations, at As-Built time only.
- `docs/IMPLEMENTATION-PLAN.md`: new Phase 15 entry, and Phase 14's stale "Unlocks: nothing further builds on this" line corrected to point here (same pattern as Phase 13→14).

## Non-goals
- No `X-Request-ID` (or similar) response header back to the client — row 37 asks for `request_id` propagated through log lines, not a client-facing correlation header; not building it unless asked.
- No change to uvicorn's own built-in HTTP access-log line format (a separate `uvicorn.access` logger) — see Open Questions, this phase's scope is the application's own logger calls unless told otherwise.
- No new logging dependency (`structlog`, `python-json-logger`, etc.) — stdlib `logging` + a custom `Formatter`, per the ladder and the phase instructions' own steer.
- No changes to any other rubric row, any other log call site not already named above, or any bonus-section item — bonus is explicitly out of scope this session per instruction.
- No rewrite of existing log call sites' messages/`extra` payloads beyond what's needed to carry `request_id` — e.g. not touching what `services/complaints.py` or `llm.py` actually log, just ensuring `request_id` rides along.

## Open Questions
1. **Scope of "every log line emitted during that request's handling" (row 37):** does this include uvicorn's own built-in HTTP access-log line (`uvicorn.access` logger, e.g. `INFO: 127.0.0.1:... "GET /api/... HTTP/1.1" 200 OK`), or is it scoped to the application's own logger calls (routes/services/repositories/providers — everything the four-layer rule actually governs)? The phase instructions name only application-level call sites (`services/complaints.py`, `providers/triage/llm.py`) as needing `request_id`, which is why the Deliverables above default to application-level scope only — but I'm flagging this rather than deciding it silently, since "every log line" could be read either way and reformatting uvicorn's own access-log output is a materially bigger (and arguably redundant, since Prometheus/`/metrics` already covers request-level observability) piece of work.
2. **Uvicorn's actual default graceful-shutdown behavior is genuinely unknown to me right now** — I have not yet read uvicorn's source/docs for its default `--timeout-graceful-shutdown` value or confirmed what it does under a real in-flight request today. This isn't a question for you; it's Plan-stage investigation work, named here only so it's visible that Deliverables' conditional Dockerfile/compose line depends on that investigation's real outcome, not a guess made now.

## Plan
(To be filled in after this Spec is approved.)

## Verification required
(To be filled in as part of the Plan.)

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md` or turns out underspecified once Plan drafting or implementation actually starts, stop and ask rather than silently resolving it.

## As-Built
(Filled in after implementation, with real command output.)
