"""Regex-based PII redaction for LLMTriage's outbound Gemini request — ADR 0004.

Provider-layer concern only (ADR 0004 "Layer ownership"): used by `LLMTriage`
immediately before it builds its outbound request. Never applied to `location`
(ADR 0004: sent unmodified) or to anything persisted/displayed — the database
always stores the citizen's original, unredacted `text`.

Known limitations (ADR 0004 "Consequences" — stated here, not silently
assumed away): misses numbers split across lines or with unusual
character-by-character spacing, and will false-positive on a non-phone digit
string shaped like a Pakistani mobile number (e.g. a reference number).
Landline numbers and names/addresses embedded in free text are out of scope
by decision, not oversight.
"""

import logging
import re

logger = logging.getLogger(__name__)

_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:(?:\+92|0092|92)[\s-]?)?0?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)"
)
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_PHONE_PLACEHOLDER = "[REDACTED-PHONE]"
_EMAIL_PLACEHOLDER = "[REDACTED-EMAIL]"


def redact(text: str) -> str:
    """Replace phone numbers and email addresses in `text` with placeholders.

    Logs only a structured fact (category + count) when a redaction fires —
    never the matched substring (ADR 0004: "never log the matched substring").
    """
    text, phone_count = _PHONE_PATTERN.subn(_PHONE_PLACEHOLDER, text)
    text, email_count = _EMAIL_PATTERN.subn(_EMAIL_PLACEHOLDER, text)
    if phone_count:
        logger.info("pii_redacted", extra={"category": "phone", "count": phone_count})
    if email_count:
        logger.info("pii_redacted", extra={"category": "email", "count": email_count})
    return text
