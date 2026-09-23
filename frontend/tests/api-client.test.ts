import { afterEach, describe, expect, it, vi } from "vitest";

import { createComplaint, getStats, updateStatus } from "../src/api/client";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client error mapping", () => {
  it("maps a 400 to a validation error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, { detail: [{ loc: ["body", "text"], msg: "too short", type: "value_error" }] }),
      ),
    );
    const result = await createComplaint({ text: "x", location: "y" });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.kind).toBe("validation");
  });

  it("maps a 409 to a transition error, naming current/attempted status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(409, {
          detail: { message: "illegal", current_status: "resolved", attempted_status: "open" },
        }),
      ),
    );
    const result = await updateStatus("id-1", "open");
    expect(result.ok).toBe(false);
    if (!result.ok && result.error.kind === "transition") {
      expect(result.error.currentStatus).toBe("resolved");
      expect(result.error.attemptedStatus).toBe("open");
    } else {
      throw new Error("expected a transition error");
    }
  });

  it("maps a 429 to a rate_limited error using the real Retry-After header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(429, { detail: "rate limit exceeded" }, { "Retry-After": "42" })),
    );
    const result = await createComplaint({ text: "a".repeat(20), location: "loc" });
    expect(result.ok).toBe(false);
    if (!result.ok && result.error.kind === "rate_limited") {
      expect(result.error.retryAfterSeconds).toBe(42);
    } else {
      throw new Error("expected a rate_limited error");
    }
  });

  it("maps an unmapped status to unknown", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(500, { detail: "boom" })));
    const result = await getStats();
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.kind).toBe("unknown");
  });

  it("maps fetch() itself throwing (network failure) to a network error, without an unhandled rejection", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const result = await getStats();
    expect(result.ok).toBe(false);
    if (!result.ok && result.error.kind === "network") {
      expect(result.error.message).toContain("Failed to fetch");
    } else {
      throw new Error("expected a network error");
    }
  });
});
