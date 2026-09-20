"""Global exception -> HTTP mapping — docs/specs/phase-07-routes.md, Open
Questions 1 and 3.

Registered once in main.py rather than as per-route try/except, so routes/
stay HTTP-only per CLAUDE.md's four-layer rule. Uses FastAPI's own
`{"detail": ...}` convention throughout rather than inventing a new envelope.
"""

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.exceptions import IllegalTransitionError, NotFoundError


async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NotFoundError)  # Starlette dispatches by registered type
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def illegal_transition_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, IllegalTransitionError)  # Starlette dispatches by registered type
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": {
                "message": str(exc),
                "current_status": exc.current_status,
                "attempted_status": exc.attempted_status,
            }
        },
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """CONTRACTS.md's POST /api/complaints row specifies 400, not FastAPI's
    default 422, for a failing request body."""
    assert isinstance(exc, RequestValidationError)  # Starlette dispatches by registered type
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": jsonable_encoder(exc.errors())},
    )
