import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Dashboard from "../src/pages/Dashboard";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const complaint = {
  id: "row-1",
  text: "A pothole has appeared on the main road.",
  location: "Test Location",
  reporter_contact: null,
  category: "roads",
  priority: "high",
  status: "open",
  ai_summary: "Pothole",
  triaged_by: "rules",
  triage_latency_ms: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  // See tests/Submit.test.tsx's afterEach for why cleanup() is manual here.
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dashboard view", () => {
  it("renders a 409 next to the acted-on row, leaving its displayed status unchanged", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(200, { items: [complaint], total: 1, page: 1, page_size: 20 }))
        .mockResolvedValueOnce(
          jsonResponse(409, {
            detail: { message: "illegal", current_status: "open", attempted_status: "resolved" },
          }),
        ),
    );
    const user = userEvent.setup();
    render(<Dashboard />);

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("open"));
    await user.click(screen.getByRole("button", { name: "resolved" }));

    await waitFor(() => expect(screen.getByText(/Cannot move from open to resolved/)).toBeTruthy());
    expect(screen.getByTestId("status").textContent).toBe("open");
  });

  it("updates the row in place on a legal transition (200)", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(200, { items: [complaint], total: 1, page: 1, page_size: 20 }))
        .mockResolvedValueOnce(jsonResponse(200, { ...complaint, status: "in_progress" }))
        .mockResolvedValueOnce(
          jsonResponse(200, {
            items: [{ ...complaint, status: "in_progress" }],
            total: 1,
            page: 1,
            page_size: 20,
          }),
        ),
    );
    const user = userEvent.setup();
    render(<Dashboard />);

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("open"));
    await user.click(screen.getByRole("button", { name: "in_progress" }));

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("in_progress"));
  });
});
