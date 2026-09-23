// Fetch wrappers for the four endpoints the three views (Submit, Dashboard,
// Stats) consume — docs/specs/phase-09-frontend-views.md's Plan. Every call
// is a relative fetch("/api/...") per docs/adr/0002-frontend-runtime-config.md:
// the frontend never holds a backend host/port/protocol anywhere.

import type {
  ApiError,
  ApiResult,
  Category,
  Complaint,
  ComplaintCreateRequest,
  PaginatedList,
  Priority,
  Stats,
  Status,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch (cause) {
    // fetch() itself threw (network failure / backend unreachable) — not an
    // HTTP error status, there is no response to branch on at all.
    return {
      ok: false,
      error: {
        kind: "network",
        message: cause instanceof Error ? cause.message : "Network request failed",
      },
    };
  }

  if (response.ok) {
    return { ok: true, data: (await response.json()) as T };
  }

  const body = await response.json().catch(() => undefined);

  let error: ApiError;
  switch (response.status) {
    case 400:
      error = { kind: "validation", status: 400, errors: body?.detail ?? [] };
      break;
    case 404:
      error = { kind: "not_found", status: 404, message: body?.detail ?? "Not found" };
      break;
    case 409:
      error = {
        kind: "transition",
        status: 409,
        message: body?.detail?.message ?? "Illegal transition",
        currentStatus: body?.detail?.current_status,
        attemptedStatus: body?.detail?.attempted_status,
      };
      break;
    case 429:
      error = {
        kind: "rate_limited",
        status: 429,
        message: body?.detail ?? "Rate limit exceeded",
        retryAfterSeconds: Number(response.headers.get("Retry-After") ?? 0),
      };
      break;
    default:
      error = { kind: "unknown", status: response.status, body };
  }
  return { ok: false, error };
}

export const createComplaint = (payload: ComplaintCreateRequest) =>
  request<Complaint>("/complaints", { method: "POST", body: JSON.stringify(payload) });

export const listComplaints = (params: {
  page?: number;
  page_size?: number;
  category?: Category;
  priority?: Priority;
  status?: Status;
}) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    query.set(key, String(value));
  }
  const qs = query.toString();
  return request<PaginatedList<Complaint>>(`/complaints${qs ? `?${qs}` : ""}`);
};

export const updateStatus = (id: string, status: Status) =>
  request<Complaint>(`/complaints/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });

export const getStats = () => request<Stats>("/stats");

// One generic, per-kind description reused by every view instead of each
// duplicating this switch (Deliverable a/b/c all need to render an ApiError
// as text). Submit still renders validation errors as a structured <ul>
// itself; every other view/kind uses this.
export function describeApiError(error: ApiError): string {
  switch (error.kind) {
    case "validation":
      return error.errors.map((e) => `${String(e.loc.at(-1))}: ${e.msg}`).join("; ");
    case "not_found":
      return error.message;
    case "transition":
      return `Cannot move from ${error.currentStatus} to ${error.attemptedStatus}: ${error.message}`;
    case "rate_limited":
      return `Try again in ${error.retryAfterSeconds}s`;
    case "network":
      return error.message;
    case "unknown":
      return `Unexpected error (status ${error.status}).`;
  }
}
