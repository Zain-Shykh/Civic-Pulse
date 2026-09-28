"""Standalone synthetic ASGI app for test_graceful_shutdown.py.

Deliberately NOT part of backend/app/ — docs/specs/
phase-15-structured-logging-and-graceful-shutdown.md's Plan, "SIGTERM test
design": no real route has a controllable delay, and adding a test-only
sleep branch to production code isn't justified by this phase's scope.
Reuses the real RequestContextMiddleware/configure_logging this phase
ships, so the test exercises the actual middleware/logging stack, not a
reimplementation of it. No DATABASE_URL/REDIS_URL/GEMINI_API_KEY needed —
app.logging_context has no such dependency.

Run via: uvicorn tests._shutdown_test_app:app --no-access-log
"""

import asyncio

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.logging_context import RequestContextMiddleware, configure_logging

configure_logging()


async def slow(request: Request) -> JSONResponse:
    await asyncio.sleep(2)
    return JSONResponse({"ok": True})


app = Starlette(routes=[Route("/slow", slow)])
app.add_middleware(RequestContextMiddleware)
