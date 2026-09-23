import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Stats from "../src/pages/Stats";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  // See tests/Submit.test.tsx's afterEach for why cleanup() is manual here.
  cleanup();
  vi.unstubAllGlobals();
});

describe("Stats view", () => {
  it("renders an arbitrary counts_by_status map generically, not a hardcoded status set", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          200,
          {
            counts_by_status: { open: 3, in_progress: 1, resolved: 0, rejected: 0, made_up_status: 7 },
            average_triage_latency_ms: 123,
          },
          { "X-Cache": "MISS" },
        ),
      ),
    );
    render(<Stats />);

    await waitFor(() => expect(screen.getByText(/average_triage_latency_ms: 123/)).toBeTruthy());
    expect(screen.getByText(/made_up_status/)).toBeTruthy();
    // cacheState is meta-information, not an aggregate — must not appear as
    // its own generic bullet alongside the real stats fields.
    expect(screen.queryByText(/cacheState/)).toBeNull();
  });

  it('renders X-Cache: HIT as "cached"', async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, { counts_by_status: {}, average_triage_latency_ms: 0 }, { "X-Cache": "HIT" }),
      ),
    );
    render(<Stats />);

    await waitFor(() => expect(screen.getByText(/Data: cached/)).toBeTruthy());
  });

  it('renders X-Cache: MISS as "fresh"', async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, { counts_by_status: {}, average_triage_latency_ms: 0 }, { "X-Cache": "MISS" }),
      ),
    );
    render(<Stats />);

    await waitFor(() => expect(screen.getByText(/Data: fresh/)).toBeTruthy());
  });
});
