"""SIGTERM drains in-flight requests before the process exits —
docs/specs/phase-15-structured-logging-and-graceful-shutdown.md, row 38.

Real subprocess: starts tests/_shutdown_test_app.py under uvicorn with the
same --no-access-log flag compose.yaml/Dockerfile use, sends it a real
in-flight request, sends the real process SIGTERM mid-flight, and checks
the response still completes successfully before the process exits — not
asserted from documentation or uvicorn's advertised defaults.
"""

import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_until_accepting(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"server on port {port} never started accepting connections")


class TestGracefulShutdown:
    def test_sigterm_drains_in_flight_request_before_exit(self) -> None:
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "tests._shutdown_test_app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=_BACKEND_DIR,
        )
        try:
            _wait_until_accepting(port)

            result: dict[str, Any] = {}

            def _send_slow_request() -> None:
                response = httpx.get(f"http://127.0.0.1:{port}/slow", timeout=10.0)
                result["status_code"] = response.status_code
                result["body"] = response.json()
                result["received_at"] = time.monotonic()

            thread = threading.Thread(target=_send_slow_request)
            thread.start()

            # /slow sleeps 2s; give it time to actually be in flight before
            # sending SIGTERM, without waiting so long it's already done.
            time.sleep(0.5)
            sigterm_sent_at = time.monotonic()
            proc.send_signal(signal.SIGTERM)

            thread.join(timeout=10.0)
            assert not thread.is_alive(), "slow request never completed"

            assert result.get("status_code") == 200
            assert result.get("body") == {"ok": True}
            assert result["received_at"] > sigterm_sent_at, (
                "response was received before SIGTERM was even sent — "
                "this proves nothing about draining"
            )

            # uvicorn's own Server.capture_signals() re-raises the original
            # signal after a graceful shutdown completes (real source read,
            # confirmed empirically here), so Python reports this process as
            # terminated BY SIGTERM (-signal.SIGTERM), not a plain exit 0 —
            # that's uvicorn correctly telling its supervisor it was asked
            # to stop, not a sign the drain failed.
            returncode = proc.wait(timeout=10.0)
            assert returncode == -signal.SIGTERM
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5.0)
