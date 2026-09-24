// docs/specs/phase-09c-visual-redesign.md's Plan §17 — Home is new page
// logic (a live stats fetch, a nav action), not a restyle of already-tested
// behavior, so it gets its own test rather than relying on OQ3's "existing
// tests survive a restyle" reasoning, which doesn't cover new code.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Home from "../src/pages/Home";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Home view", () => {
  it("renders the stat row from a real getStats response, not hardcoded numbers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          counts_by_status: { open: 5, in_progress: 2, resolved: 3, rejected: 0 },
          average_triage_latency_ms: 250,
        }),
      ),
    );
    render(<Home onNavigate={() => {}} />);

    await waitFor(() => expect(screen.getByText("10")).toBeTruthy());
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText("250ms")).toBeTruthy();
  });

  it('calls onNavigate("submit") when "Report an issue" is clicked', async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { counts_by_status: {}, average_triage_latency_ms: 0 })),
    );
    const onNavigate = vi.fn();
    const user = userEvent.setup();
    render(<Home onNavigate={onNavigate} />);

    await user.click(screen.getByRole("button", { name: /report an issue/i }));

    expect(onNavigate).toHaveBeenCalledWith("submit");
  });
});
