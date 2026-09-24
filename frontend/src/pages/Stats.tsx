// docs/specs/phase-09-frontend-views.md, Deliverable (c). Renders whatever
// GET /api/stats returns generically — no hardcoded assumption of exactly
// which status keys exist. Addendum: surfaces X-Cache as a plain-language
// freshness indicator ("fresh"/"cached"), not the raw HIT/MISS header value
// — see the Addendum's "Wording" section for why. Restyled in
// docs/specs/phase-09c-visual-redesign.md — same logic, new markup only.
import { useEffect } from "react";

import { describeApiError, getStats } from "../api/client";
import { useApiCall } from "../hooks/useApiCall";

function cacheStateLabel(cacheState: "HIT" | "MISS" | null): string {
  if (cacheState === "HIT") return "cached";
  if (cacheState === "MISS") return "fresh";
  return "unknown";
}

export default function Stats() {
  const [state, run] = useApiCall(getStats);

  useEffect(() => {
    run();
  }, [run]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h2 className="text-2xl font-semibold text-ink">Stats</h2>
      {state.status === "loading" && <p className="mt-4">Loading…</p>}
      {state.status === "error" && (
        <p role="alert" className="mt-4 text-priority-high">
          {describeApiError(state.error)}
        </p>
      )}
      {state.status === "success" && (
        <>
          <p className="mt-4 text-sm text-ink-secondary">Data: {cacheStateLabel(state.data.cacheState)}</p>
          <ul className="mt-2 space-y-1 font-mono text-sm text-ink">
            {Object.entries(state.data)
              .filter(([key]) => key !== "cacheState")
              .map(([key, value]) => (
                <li key={key}>
                  {key}: {typeof value === "object" ? JSON.stringify(value) : String(value)}
                </li>
              ))}
          </ul>
        </>
      )}
    </div>
  );
}
