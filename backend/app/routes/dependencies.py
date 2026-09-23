"""Shared route dependencies — docs/specs/phase-07-routes.md, Open Question 4.

The TriageProvider is constructed once at app startup (main.py's lifespan)
and stored on app.state; routes read the same instance back on every
request rather than re-invoking the factory per request. Safe to share:
LLMTriage.__init__ sets only fixed attributes, and .triage() never assigns
to self. (Confirmed directly against providers/triage/llm.py.)
"""

from typing import Annotated

from fastapi import Depends, Request

from app.providers.triage.base import TriageProvider


def get_triage_provider(request: Request) -> TriageProvider:
    return request.app.state.triage_provider  # type: ignore[no-any-return]


TriageProviderDep = Annotated[TriageProvider, Depends(get_triage_provider)]
