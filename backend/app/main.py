"""CivicPulse backend entrypoint.

Walking-skeleton phase: only /health and /ready are wired up. Structured
logging, request-id propagation, graceful SIGTERM shutdown, and the real
API routes arrive in the Backend Core phase, each with its own spec.
"""

from fastapi import FastAPI

from app.routes.health import router as health_router

app = FastAPI(title="CivicPulse")
app.include_router(health_router)
