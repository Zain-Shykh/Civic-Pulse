# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
WORKDIR /build

# Deps copied and installed before source, so this layer only invalidates
# when pyproject.toml changes, not on every source edit.
COPY pyproject.toml ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip \
    && python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); print('\n'.join(d['project']['dependencies']))" > requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip setuptools wheel

FROM python:3.12-slim AS runtime

RUN groupadd --system civicpulse && useradd --system --gid civicpulse --home /app civicpulse

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# This runtime stage's own base-image-provided system-level pip (outside
# /opt/venv, never on PATH below) is never invoked, but still ships its own
# vendored msgpack -- same class of finding as the builder stage's venv-
# seeded pip (see above): both are unused at runtime, both were real HIGH
# CVE hits (GHSA-6v7p-g79w-8964, CVE-2025-47273) confirmed by actually
# running the scan job's Trivy check and tracing the flagged files with
# `find / -iname`, not guessed. Removed for the same reason.
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip \
           /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
           /usr/local/bin/pip3 /usr/local/bin/pip3.*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER civicpulse
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
