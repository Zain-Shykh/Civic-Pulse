# Phase 15: Structured logging + graceful shutdown
Status: not started
Depends on: Phase 7 (routes/main.py wiring — where cross-cutting middleware lives), Phase 6 (service-layer log calls this must propagate through), Phase 5b (LLMTriage/redaction log calls this must propagate through), Phase 11 (k8s `terminationGracePeriodSeconds: 30` + `preStop: sleep 5` already in `k8s/base/backend.yaml`, the environment row 38's SIGTERM behavior runs inside)
Reads first: `docs/RUBRIC-CHECKLIST.md` rows 37/38, `docs/CONTRACTS.md` (four-layer rule), `backend/app/main.py`, `backend/app/services/complaints.py`, `backend/app/providers/triage/llm.py`, `backend/app/providers/triage/redaction.py`

## Goal
Close two real, disclosed Category C gaps for real: (1) every log line emitted by the backend during a request's handling is a structured JSON object on stdout carrying a per-request `request_id`, including log calls that already exist today and are not being touched otherwise; (2) SIGTERM causes in-flight requests to finish and respond successfully before the process exits, verified by an actual subprocess-level test, not asserted from documentation or uvicorn's advertised defaults.

## Deliverables
- `backend/app/logging_context.py` (new): a JSON `logging.Formatter`, a per-request `request_id` (stdlib `contextvars`, not threaded through function signatures), a `logging.Filter` that injects the current request's `request_id` into every `LogRecord`, a raw ASGI middleware class that generates the `request_id`, times the request, and — replacing uvicorn's own access log — emits one structured completion line (`method`, `path`, `status_code`, `duration_ms`, `request_id`), and a `configure_logging()` entrypoint that attaches the JSON handler to the root logger. `backend/app/services/complaints.py`'s existing `logger.warning(...)`, `backend/app/providers/triage/llm.py`'s two `logger.warning`/`logger.info` calls, and `backend/app/providers/triage/redaction.py`'s two `logger.info` calls all carry `request_id` through this without editing their call sites — none of those three files are touched.
- `backend/app/main.py`: call `configure_logging()` at module level, add the ASGI middleware via `app.add_middleware(...)`.
- `backend/Dockerfile` CMD and `compose.yaml`'s backend `command:` override: add `--no-access-log`, per your decision to suppress uvicorn's own access log and own that line ourselves.
- `backend/tests/test_logging.py` (new): real tests proving a request produces structured JSON log lines on stdout, that two log lines from the same request (the completion line plus an existing call site forced to fire, e.g. the triage fallback warning) share one `request_id`, and that the JSON is well-formed and parseable.
- `backend/tests/_shutdown_test_app.py` (new, not collected as a test module) + `backend/tests/test_graceful_shutdown.py` (new): see "SIGTERM test design" below.
- `docs/RUBRIC-CHECKLIST.md` rows 37 and 38 flipped to `[x]` with real citations, at As-Built time only.
- `docs/IMPLEMENTATION-PLAN.md`: new Phase 15 entry, and Phase 14's stale "Unlocks: nothing further builds on this" line corrected to point here (same pattern as Phase 13→14) — **already done** in the Spec commit.

## Non-goals
- No `X-Request-ID` (or similar) response header back to the client — row 37 asks for `request_id` propagated through log lines, not a client-facing correlation header; not building it unless asked.
- No reformatting of uvicorn's own `uvicorn`/`uvicorn.error` startup/shutdown banner lines ("Started server process", "Uvicorn running on...") — those aren't emitted during a request's handling, they're process lifecycle messages outside any request; only `uvicorn.access` (which fires per-request) is suppressed and replaced.
- No new logging dependency (`structlog`, `python-json-logger`, etc.) — stdlib `logging` + a custom `Formatter`.
- No changes to any other rubric row, any other log call site not already named above, or any bonus-section item.
- No rewrite of existing log call sites' messages/`extra` payloads beyond what's needed to carry `request_id`.
- No test-only delay/sleep code added to any real route in `backend/app/` — the SIGTERM test's slow endpoint lives entirely in `backend/tests/`, never in production code.

## Open Questions — both now resolved
1. **Scope of "every log line" / uvicorn's access log — RESOLVED by you:** replace uvicorn's default access log with our own structured completion line via the middleware being built anyway; suppress uvicorn's own `uvicorn.access` output (`--no-access-log`), don't reformat it in place. Reflected in Deliverables/Non-goals above.
2. **Uvicorn's real default graceful-shutdown behavior — investigated, not guessed:** read `uvicorn==0.53.0`'s actual installed source (`.venv/lib/.../uvicorn/config.py`, `server.py`). `Config.__init__`'s default is `timeout_graceful_shutdown: int | None = None`. `Server.shutdown()` (real source, quoted in full during Plan drafting): on receiving SIGTERM, `handle_exit` sets `should_exit = True`; the server stops accepting new connections, calls `connection.shutdown()` on every in-flight connection, then `await asyncio.wait_for(self._wait_tasks_to_complete(), timeout=self.config.timeout_graceful_shutdown)`. With the default `None`, `asyncio.wait_for(..., timeout=None)` waits **indefinitely** — i.e. the out-of-the-box default already drains in-flight requests to completion before the lifespan-shutdown/exit sequence continues, no explicit flag needed. `SIGTERM` is confirmed present in `uvicorn.server.HANDLED_SIGNALS` (`(SIGINT, SIGTERM)`). This is a real code-read finding, not an assumption — still verified empirically below, per your instruction, rather than trusted on the source read alone.

## Plan

**Files touched, in order:**
1. `backend/app/logging_context.py` (new) — the module described in Deliverables.
2. `backend/app/main.py` — two-line wiring: `configure_logging()` call, `app.add_middleware(RequestContextMiddleware)`.
3. `backend/Dockerfile`, `compose.yaml` — append `--no-access-log` to the existing uvicorn command lines.
4. `backend/tests/_shutdown_test_app.py` (new) — the synthetic slow ASGI app for the SIGTERM test.
5. `backend/tests/test_graceful_shutdown.py` (new).
6. `backend/tests/test_logging.py` (new).
7. `docs/RUBRIC-CHECKLIST.md` rows 37/38 — last, at As-Built time, after real verification output exists to cite.

**Key technical choices and why:**

- **Request-id propagation: `contextvars` + a `logging.Filter`, not a parameter threaded through call signatures.** This is what keeps it out of `services/`/`repositories/`/`providers/` entirely — none of those layers' functions gain a `request_id` parameter, and none of their existing `logger.warning(...)`/`logger.info(...)` call sites change. The `Filter` reads the contextvar at log-emit time and stamps it onto the `LogRecord`; any logger anywhere in the process that propagates to the root logger (all of them do today — no module calls `logging.getLogger(...).propagate = False`) picks this up automatically.
- **Raw ASGI middleware (a plain class implementing `__call__(scope, receive, send)`), not `@app.middleware("http")`/`BaseHTTPMiddleware`.** Starlette's `BaseHTTPMiddleware` runs the downstream app via a `call_next()` that internally streams the response through a separately-scheduled task — a well-documented source of subtle `contextvars`/request-state propagation issues. A raw ASGI middleware calls `await self.app(scope, receive, send_wrapper)` directly in the same coroutine, so the `request_id` contextvar set before that call is guaranteed visible to every line of code the request touches, including deep in `services/`/`providers/`, with no task-boundary in between. `send` is wrapped only to capture the real status code off the `http.response.start` ASGI message, for the completion log line.
- **JSON formatter's "extra fields" handling:** a `logging.LogRecord`'s standard attribute set is computed once at import time (`vars(logging.LogRecord("", 0, "", 0, "", (), None))`), and the formatter includes any attribute *not* in that set (i.e. anything passed via a call's `extra={...}`) in the JSON output. This is what makes `services/complaints.py`'s `extra={"provider": ...}` and `redaction.py`'s `extra={"category": ..., "count": ...}` show up as real structured fields, not just get silently dropped.
- **Suppressing uvicorn's access log:** `--no-access-log` on the uvicorn command line (confirmed real CLI flag via `python -m uvicorn --help`, maps to `Config(access_log=False)`), added to both `backend/Dockerfile`'s `CMD` (governs `compose.prod.yaml` and the k8s image) and `compose.yaml`'s dev `command:` override (which repeats the full command line rather than inheriting the Dockerfile's `CMD`). `uvicorn`/`uvicorn.error` (the process-lifecycle loggers, not per-request) are left untouched — see Non-goals.
- **SIGTERM test design:** no existing route has a natural, controllable delay, and adding a test-only sleep branch to a real route in `backend/app/` isn't justified by this phase's scope. Instead, `backend/tests/_shutdown_test_app.py` is a standalone few-line ASGI app — imports the real `RequestContextMiddleware`/`configure_logging` from `backend/app/logging_context.py` (so the test exercises the actual middleware/logging stack this phase ships, not a reimplementation) plus one trivial route that `await asyncio.sleep(2)` before responding `200`. `test_graceful_shutdown.py` launches it via `subprocess.Popen([sys.executable, "-m", "uvicorn", "tests._shutdown_test_app:app", "--host", "127.0.0.1", "--port", <free port>, "--no-access-log"], cwd=backend/)`, waits for it to accept connections, fires the slow request from a background thread via `httpx`, sleeps briefly (well under 2s) on the main thread, sends the subprocess `SIGTERM`, then asserts: the response actually completes with `200` and the expected body: the subprocess exits (`proc.wait(timeout=...)`) with code `0` shortly after; and — the actual point of the test — the response is received *after* the SIGTERM was sent, proving the request was drained rather than the process dying mid-response. No Postgres/Redis needed for this test; it exercises the ASGI-server/middleware layer only, which is what SIGTERM-draining actually is a property of, not any specific route's business logic.
- **Dockerfile/compose command changes beyond `--no-access-log`:** none anticipated, since the source-level finding above says the default `timeout_graceful_shutdown=None` already does the right thing — but this is exactly what the SIGTERM test empirically confirms or refutes before the As-Built claims it. If the real test shows a problem, the Dockerfile/compose command gets an explicit `--timeout-graceful-shutdown <n>` and that deviation is written up with the real evidence, not silently patched over.

**Open uncertainties:** none — both Open Questions above are resolved (one by you, one by source investigation to be confirmed empirically in Implementation).

## Verification required
- `cd backend && ruff check app/ tests/ && mypy app/` — no new lint/type errors.
- `cd backend && TRIAGE_PROVIDER=simulated pytest --cov=app --cov-report=term-missing --cov-fail-under=65` against real throwaway `postgres:16-alpine`/`redis:7-alpine` containers (same pattern as Phase 14) — full suite still green, coverage still ≥65%, real pasted output in the As-Built.
- `cd backend && pytest tests/test_logging.py tests/test_graceful_shutdown.py -v` — real pasted output for both new files specifically.
- A live end-to-end check against the real compose stack: `docker compose up -d --build`, then `curl` a real request (including one that forces the `triage_provider_raised_falling_back` warning path), then `docker compose logs backend` — real pasted JSON log lines showing the completion line and the pre-existing warning sharing one `request_id`, and confirming `uvicorn.access`'s old plain-text line is gone.
- `docker compose kill -s SIGTERM backend` (or equivalent) during a real in-flight request against the live compose stack, if practically reproducible, as a second, real-environment data point alongside the subprocess test — not a substitute for it.

## Ambiguity handling
If anything here conflicts with `docs/CONTRACTS.md` or turns out underspecified once Plan drafting or implementation actually starts, stop and ask rather than silently resolving it.

## As-Built
(Filled in after implementation, with real command output.)
