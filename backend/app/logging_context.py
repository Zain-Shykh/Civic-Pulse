"""Structured JSON logging + per-request request_id — docs/specs/
phase-15-structured-logging-and-graceful-shutdown.md.

Cross-cutting concern, deliberately not part of routes/services/repositories/
providers (the four-layer rule, docs/CONTRACTS.md): request_id lives in a
contextvar, not a function parameter, so nothing in those layers changes to
carry it. Any `logging.getLogger(__name__)` call anywhere in the process
(services/complaints.py, providers/triage/llm.py, providers/triage/
redaction.py, and any future one) picks it up automatically, because none of
them set `propagate = False` or attach their own handler — they all flow up
to the root logger this module configures.
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

request_logger = logging.getLogger("app.request")

# Every attribute a plain LogRecord already has — anything else on a record
# (i.e. passed via a call's own `extra={...}`) is a real structured field,
# not log-internal bookkeeping.
_STANDARD_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class RequestContextMiddleware:
    """Raw ASGI middleware, not Starlette's BaseHTTPMiddleware/call_next —
    that implementation streams the response through a separately-scheduled
    task, a documented source of contextvar-propagation surprises. Calling
    `self.app(...)` directly keeps the whole request in one coroutine, so
    request_id sees no task boundary before it reaches services/providers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        token = request_id_var.set(request_id)
        status_holder: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status_code"] = message["status"]
            await send(message)

        start = time.monotonic()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            request_logger.info(
                "request_completed",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_holder.get("status_code"),
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(token)
