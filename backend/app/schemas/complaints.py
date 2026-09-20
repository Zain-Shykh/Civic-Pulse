"""Request models for routes/complaints.py — docs/specs/phase-07-routes.md.

Field bounds copied verbatim from docs/CONTRACTS.md §2.3's schema table, not
invented here.
"""

from pydantic import BaseModel, Field


class ComplaintCreateRequest(BaseModel):
    text: str = Field(min_length=10, max_length=2000)
    location: str = Field(min_length=3, max_length=200)
    reporter_contact: str | None = None


class StatusUpdateRequest(BaseModel):
    status: str
