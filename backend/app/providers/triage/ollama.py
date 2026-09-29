"""OllamaTriage — offline triage path backed by a local Ollama server.

Real implementation, Phase 16. Single attempt, no retry, 5-second timeout
(Plan point 3 — a local process is either up or genuinely down/overloaded;
retrying inside the same request rarely helps the way retrying a
rate-limited remote API does). Falls back to RuleBasedTriage on any
failure, with the same tag-normalization the LLMTriage fallback block uses
(Plan point 1) rather than a shared helper — one line, duplicated by choice
(Plan point 5).
"""

import logging

import httpx
from pydantic import ValidationError

from app.providers.triage.base import TriageProvider, TriageResult
from app.providers.triage.prompting import SYSTEM_INSTRUCTION, TriageResponseSchema
from app.providers.triage.redaction import redact
from app.providers.triage.rules import RuleBasedTriage

logger = logging.getLogger(__name__)

_MODEL = "qwen2.5:0.5b"
_TIMEOUT_SECONDS = 5.0


class OllamaTriage:
    name = "llm:ollama"

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        fallback: TriageProvider | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT_SECONDS)
        self._fallback: TriageProvider = fallback or RuleBasedTriage()

    async def triage(self, text: str, location: str) -> TriageResult:
        redacted_text = redact(text)
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": _MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                        {"role": "user", "content": redacted_text},
                    ],
                    "format": "json",
                    "stream": False,
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            parsed = TriageResponseSchema.model_validate_json(content)
            return TriageResult(
                category=parsed.category,
                priority=parsed.priority,
                summary=parsed.summary,
                confidence=parsed.confidence,
                triaged_by="llm:ollama",
            )
        except (httpx.HTTPError, ValidationError, KeyError) as exc:
            logger.warning("ollama_triage_call_failed", extra={"exception": type(exc).__name__})

        fallback_result = await self._fallback.triage(text, location)
        triaged_by = (
            "rules:fallback"
            if fallback_result.triaged_by == "rules"
            else fallback_result.triaged_by
        )
        return TriageResult(
            category=fallback_result.category,
            priority=fallback_result.priority,
            summary=fallback_result.summary,
            confidence=fallback_result.confidence,
            triaged_by=triaged_by,
        )
