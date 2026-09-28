"""Structured JSON logging + request_id propagation —
docs/specs/phase-15-structured-logging-and-graceful-shutdown.md, row 37.

JsonFormatter itself is tested in isolation (no app/DB needed). request_id
correlation is tested over a real HTTP request through the actual app,
forcing the same triage-fallback path test_routes_complaints.py's
TestMandatoryDeterminism already exercises — so what gets checked for
request_id is an existing (not newly added) logger.warning call site in
services/complaints.py, per the spec's own requirement.
"""

import json
import logging
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.logging_context import JsonFormatter, RequestIdFilter, request_id_var
from app.main import app
from app.providers.triage.simulated import SimulatedTriage
from app.routes.dependencies import get_triage_provider

# Own dedicated IP, distinct from every other test file's
# (docs/specs/phase-08-cache-layer.md's Plan, "Test isolation for the rate
# limiter") so this file's requests never share a rate-limit bucket with
# another file's.
_FILE_CLIENT_IP = "10.0.0.20"
_DELETE = text("DELETE FROM complaints WHERE id = :id")


async def _delete(complaint_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(_DELETE, {"id": complaint_id})


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, headers={"X-Real-IP": _FILE_CLIENT_IP}) as c:
        yield c
    app.dependency_overrides.clear()


def _make_record(msg: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=(), exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    RequestIdFilter().filter(record)
    return record


class TestJsonFormatter:
    def test_formats_valid_json_with_request_id_and_extra_fields(self) -> None:
        token = request_id_var.set("test-request-id-123")
        try:
            record = _make_record("something_happened", category="phone", count=2)
            formatted = JsonFormatter().format(record)
        finally:
            request_id_var.reset(token)

        payload = json.loads(formatted)
        assert payload["message"] == "something_happened"
        assert payload["level"] == "INFO"
        assert payload["logger"] == "app.test"
        assert payload["request_id"] == "test-request-id-123"
        assert payload["category"] == "phone"
        assert payload["count"] == 2

    def test_omits_request_id_outside_any_request_context(self) -> None:
        record = _make_record("no_request_here")
        payload = json.loads(JsonFormatter().format(record))
        assert payload["request_id"] is None


class TestRequestIdPropagation:
    """Row 37: request_id generated per request, propagated through every
    log line emitted during that request's handling — including a
    pre-existing call site, not just newly-added ones."""

    async def test_completion_line_and_existing_fallback_warning_share_one_request_id(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        app.dependency_overrides[get_triage_provider] = lambda: SimulatedTriage(
            always_raise=True
        )
        try:
            with caplog.at_level(logging.INFO):
                response = client.post(
                    "/api/complaints",
                    json={
                        "text": "Phase 15's own request_id correlation check, "
                        "provider broken on purpose.",
                        "location": "Test Location",
                    },
                )
            assert response.status_code == 201
            body = response.json()
            try:
                assert body["triaged_by"] == "rules:fallback"

                completion = [
                    r for r in caplog.records if r.getMessage() == "request_completed"
                ]
                fallback_warning = [
                    r
                    for r in caplog.records
                    if r.getMessage() == "triage_provider_raised_falling_back"
                ]
                assert len(completion) == 1
                assert len(fallback_warning) == 1
                assert completion[0].request_id is not None
                assert completion[0].request_id == fallback_warning[0].request_id
                assert completion[0].status_code == 201
                assert completion[0].method == "POST"
                assert completion[0].path == "/api/complaints"
                assert isinstance(completion[0].duration_ms, int)
            finally:
                await _delete(uuid.UUID(body["id"]))
        finally:
            app.dependency_overrides.clear()

    def test_two_separate_requests_get_different_request_ids(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO):
            client.get("/health")
            client.get("/health")
        completions = [r for r in caplog.records if r.getMessage() == "request_completed"]
        assert len(completions) == 2
        assert completions[0].request_id != completions[1].request_id
        assert all(r.request_id is not None for r in completions)
