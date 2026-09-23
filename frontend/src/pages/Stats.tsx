// docs/specs/phase-09-frontend-views.md, Deliverable (c). Renders whatever
// GET /api/stats returns generically — no hardcoded assumption of exactly
// which status keys exist. Addendum: surfaces X-Cache as a plain-language
// freshness indicator ("fresh"/"cached"), not the raw HIT/MISS header value
// — see the Addendum's "Wording" section for why.
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
    <div>
      <h2>Stats</h2>
      {state.status === "loading" && <p>Loading…</p>}
      {state.status === "error" && <p role="alert">{describeApiError(state.error)}</p>}
      {state.status === "success" && (
        <>
          <p>Data: {cacheStateLabel(state.data.cacheState)}</p>
          <ul>
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
