// docs/specs/phase-09c-visual-redesign.md's Plan §14 (Deliverable d). The
// stat row reuses Phase 9's own getStats/useApiCall — a second call site of
// the same hook and client function, not a new endpoint (see the spec's
// Non-goals).
import { useEffect } from "react";

import { getStats } from "../api/client";
import { CATEGORIES } from "../api/types";
import type { View } from "../App";
import { useApiCall } from "../hooks/useApiCall";
import { Button } from "../components/ui/button";

export default function Home({ onNavigate }: { onNavigate: (view: View) => void }) {
  const [state, run] = useApiCall(getStats);

  useEffect(() => {
    run();
  }, [run]);

  const totals = state.status === "success" ? state.data.counts_by_status : {};
  const totalComplaints = Object.values(totals).reduce((sum, n) => sum + n, 0);
  const openNow = totals.open ?? 0;
  const averageLatency =
    state.status === "success" ? Math.round(state.data.average_triage_latency_ms) : undefined;

  return (
    <div>
      <section className="relative overflow-hidden bg-background px-4 py-16 text-center">
        <svg
          viewBox="0 0 400 100"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-24 w-full text-primary opacity-10"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M0 100V60l20-10v20l20-30v40l20-15v15l30-25v25l25-10v10l40-20v20l30-5v5l40-15v15l40-8v8l40-18v18l40-10v10l25-6v6l40-12v12H0z" />
        </svg>
        <div className="relative mx-auto max-w-2xl">
          <h1 className="text-4xl font-bold text-ink">Report a civic issue. Track what happens next.</h1>
          <p className="mt-4 text-lg text-ink-secondary">
            Submit a complaint about a local issue and follow it from report to resolution.
          </p>
          <Button className="mt-6" onClick={() => onNavigate("submit")}>
            Report an issue
          </Button>
        </div>
      </section>

      <section className="border-y border-border">
        <div className="mx-auto grid max-w-3xl grid-cols-1 divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <div className="px-4 py-6 text-center">
            <p className="font-mono text-3xl font-semibold text-primary">{totalComplaints}</p>
            <p className="text-sm text-ink-secondary">Complaints reported</p>
          </div>
          <div className="px-4 py-6 text-center">
            <p className="font-mono text-3xl font-semibold text-primary">{openNow}</p>
            <p className="text-sm text-ink-secondary">Open right now</p>
          </div>
          <div className="px-4 py-6 text-center">
            <p className="font-mono text-3xl font-semibold text-primary">
              {averageLatency !== undefined ? `${averageLatency}ms` : "—"}
            </p>
            <p className="text-sm text-ink-secondary">Average triage time</p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-4 py-10 text-center">
        <p className="text-ink-secondary">
          You can report issues about {CATEGORIES.join(", ")}, and more.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-4 py-10">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          <div className="text-center">
            <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full bg-primary text-white">
              1
            </div>
            <h3 className="mt-3 font-semibold text-ink">Report it</h3>
            <p className="mt-1 text-sm text-ink-secondary">Describe the issue and where it is.</p>
          </div>
          <div className="text-center">
            <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full bg-primary text-white">
              2
            </div>
            <h3 className="mt-3 font-semibold text-ink">Triaged automatically</h3>
            <p className="mt-1 text-sm text-ink-secondary">
              Your report is categorized and prioritized right away.
            </p>
          </div>
          <div className="text-center">
            <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full bg-primary text-white">
              3
            </div>
            <h3 className="mt-3 font-semibold text-ink">Operators act on it</h3>
            <p className="mt-1 text-sm text-ink-secondary">
              City staff track and resolve it on the dashboard.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
