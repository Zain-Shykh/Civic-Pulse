import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import Submit from "../src/pages/Submit";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  // globals: false (docs/specs/phase-09-frontend-views.md's Plan) means
  // Testing Library's automatic afterEach-based cleanup never gets
  // registered — without this, each test's render stacks on the last.
  cleanup();
  vi.unstubAllGlobals();
});

describe("Submit view", () => {
  it("renders the 201 response's triage result inline, no second request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(201, {
        id: "abc",
        category: "roads",
        priority: "high",
        ai_summary: "Pothole reported",
        triaged_by: "rules",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<Submit />);

    await user.type(screen.getByLabelText(/text/i), "A pothole has appeared on the main road.");
    await user.type(screen.getByLabelText(/location/i), "Test Location");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(screen.getByText(/Category: roads/)).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("renders the 400 field-level errors as a generic list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, { detail: [{ loc: ["body", "text"], msg: "too short", type: "value_error" }] }),
      ),
    );
    const user = userEvent.setup();
    render(<Submit />);

    await user.type(screen.getByLabelText(/text/i), "short");
    await user.type(screen.getByLabelText(/location/i), "loc");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(screen.getByText(/too short/)).toBeTruthy());
  });

  it("renders the 429 message using the real Retry-After value", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(429, { detail: "rate limit exceeded" }, { "Retry-After": "17" })),
    );
    const user = userEvent.setup();
    render(<Submit />);

    await user.type(screen.getByLabelText(/text/i), "A pothole has appeared on the main road.");
    await user.type(screen.getByLabelText(/location/i), "Test Location");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(screen.getByText(/Try again in 17s/)).toBeTruthy());
  });
});
