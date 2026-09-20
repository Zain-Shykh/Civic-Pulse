"""TriageProvider Protocol and TriageResult schema — docs/CONTRACTS.md §2.5.

Category/Priority live here rather than a shared module because this is the
only consumer so far (see docs/specs/phase-05a-deterministic-triage.md's Plan).
"""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field


class Category(StrEnum):
    WATER = "water"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    ROADS = "roads"
    STREETLIGHTS = "streetlights"
    OTHER = "other"


class Priority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TriageResult(BaseModel):
    category: Category
    priority: Priority
    summary: str = Field(max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)
    triaged_by: str


class TriageProvider(Protocol):
    name: str

    def triage(self, text: str, location: str) -> TriageResult: ...
