// docs/specs/phase-09-frontend-views.md, Deliverable (a). Submits, then
// renders exactly what POST /api/complaints returned or rejected — no
// client-side re-validation of the length limits that live in the backend
// (docs/CONTRACTS.md's schema table). Restyled in
// docs/specs/phase-09c-visual-redesign.md — same logic, new markup only.
import { useState, type FormEvent } from "react";

import { createComplaint, describeApiError } from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
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
    <div className="mx-auto max-w-xl px-4 py-10">
      <h2 className="text-2xl font-semibold text-ink">Submit a complaint</h2>
      <p className="mt-1 text-sm text-ink-muted">
        This form is for non-emergency civic issues only. In an emergency, contact local emergency services
        directly.
      </p>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">Text</span>
          <Textarea className="mt-1" value={text} onChange={(e) => setText(e.target.value)} required />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">Location</span>
          <Input className="mt-1" value={location} onChange={(e) => setLocation(e.target.value)} required />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">Reporter contact (optional)</span>
          <Input
            className="mt-1"
            value={reporterContact}
            onChange={(e) => setReporterContact(e.target.value)}
          />
        </label>
        <Button type="submit" disabled={state.status === "loading"}>
          {state.status === "loading" ? "Submitting…" : "Submit"}
        </Button>
      </form>

      {state.status === "success" && (
        <div role="status" className="mt-6 space-y-1 rounded-md border border-border p-4">
          <p>Category: {state.data.category}</p>
          <p>Priority: {state.data.priority}</p>
          <p>Summary: {state.data.ai_summary}</p>
          <p>Triaged by: {state.data.triaged_by}</p>
        </div>
      )}

      {state.status === "error" && (
        <div role="alert" className="mt-6 rounded-md border border-priority-high p-4 text-priority-high">
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
