// docs/specs/phase-09-frontend-views.md, Deliverable (a). Submits, then
// renders exactly what POST /api/complaints returned or rejected — no
// client-side re-validation of the length limits that live in the backend
// (docs/CONTRACTS.md's schema table).
import { useState, type FormEvent } from "react";

import { createComplaint, describeApiError } from "../api/client";
import { useApiCall } from "../hooks/useApiCall";

export default function Submit() {
  const [text, setText] = useState("");
  const [location, setLocation] = useState("");
  const [reporterContact, setReporterContact] = useState("");
  const [state, run] = useApiCall(createComplaint);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run({ text, location, reporter_contact: reporterContact || null });
  }

  return (
    <div>
      <h2>Submit a complaint</h2>
      <form onSubmit={handleSubmit}>
        <label>
          Text
          <textarea value={text} onChange={(e) => setText(e.target.value)} required />
        </label>
        <label>
          Location
          <input value={location} onChange={(e) => setLocation(e.target.value)} required />
        </label>
        <label>
          Reporter contact (optional)
          <input value={reporterContact} onChange={(e) => setReporterContact(e.target.value)} />
        </label>
        <button type="submit" disabled={state.status === "loading"}>
          {state.status === "loading" ? "Submitting…" : "Submit"}
        </button>
      </form>

      {state.status === "success" && (
        <div role="status">
          <p>Category: {state.data.category}</p>
          <p>Priority: {state.data.priority}</p>
          <p>Summary: {state.data.ai_summary}</p>
          <p>Triaged by: {state.data.triaged_by}</p>
        </div>
      )}

      {state.status === "error" && (
        <div role="alert">
          {state.error.kind === "validation" ? (
            <ul>
              {state.error.errors.map((item, index) => (
                <li key={index}>
                  {String(item.loc.at(-1))}: {item.msg}
                </li>
              ))}
            </ul>
          ) : (
            <p>{describeApiError(state.error)}</p>
          )}
        </div>
      )}
    </div>
  );
}
