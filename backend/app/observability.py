"""Custom Prometheus metrics — docs/specs/phase-07b-metrics.md.

Generic request count/latency come from prometheus-fastapi-instrumentator
(wired in main.py). These two are the triage-specific pair CONTRACTS.md
§2.2's /metrics row also requires; they're declared on the default
Prometheus registry (no CollectorRegistry passed) so instrumentator's
Instrumentator().expose(app) picks them up automatically alongside its own
metrics — no separate route needed.
"""

from prometheus_client import Counter, Histogram

TRIAGE_LATENCY_SECONDS = Histogram(
    "triage_latency_seconds", "Time spent in the triage provider call, in seconds."
)
TRIAGE_FALLBACK_TOTAL = Counter(
    "triage_fallback_total", "Count of complaints triaged via the rules-based fallback."
)
