// docs/specs/phase-09-frontend-views.md, Deliverable (c). Renders whatever
// GET /api/stats returns generically — no hardcoded assumption of exactly
// which status keys exist. Deliberately does not surface the X-Cache header
// (see spec's Non-goals — checked, no requirement found either way).
import { useEffect } from "react";

import { describeApiError, getStats } from "../api/client";
import { useApiCall } from "../hooks/useApiCall";

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
        <ul>
          {Object.entries(state.data).map(([key, value]) => (
            <li key={key}>
              {key}: {typeof value === "object" ? JSON.stringify(value) : String(value)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
