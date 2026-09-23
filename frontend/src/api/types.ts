// Hand-typed against docs/CONTRACTS.md (docs/specs/phase-09-frontend-views.md,
// Open Question 3), cross-checked against the backend's live /openapi.json at
// review time. Enum value lists live here as schema/type knowledge only — see
// Open Question 6: the status-transition *decision* never lives in the
// frontend, only these value lists do.

export type Category = "water" | "electricity" | "sanitation" | "roads" | "streetlights" | "other";
export type Priority = "high" | "normal" | "low";
export type Status = "open" | "in_progress" | "resolved" | "rejected";

export interface Complaint {
  id: string;
  text: string;
  location: string;
  reporter_contact: string | null;
  category: Category;
  priority: Priority;
  status: Status;
  ai_summary: string | null;
  triaged_by: string;
  triage_latency_ms: number;
  created_at: string;
  updated_at: string;
}

export interface ComplaintCreateRequest {
  text: string;
  location: string;
  reporter_contact?: string | null;
}

export interface PaginatedList<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Stats {
  counts_by_status: Record<string, number>;
  average_triage_latency_ms: number;
  [key: string]: unknown;
}

// docs/specs/phase-09-frontend-views.md's Addendum. HIT/MISS mirrors
// GET /api/stats's X-Cache header (docs/specs/phase-08-cache-layer.md);
// null covers a missing/unexpected header value defensively.
export type CacheState = "HIT" | "MISS" | null;

export interface StatsWithCacheState extends Stats {
  cacheState: CacheState;
}

// Mirrors backend/app/exception_handlers.py's validation_error_handler:
// {"detail": jsonable_encoder(exc.errors())} — FastAPI's default
// RequestValidationError item shape.
export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export type ApiError =
  | { kind: "validation"; status: 400; errors: ValidationErrorItem[] }
  | { kind: "not_found"; status: 404; message: string }
  | { kind: "transition"; status: 409; message: string; currentStatus: Status; attemptedStatus: Status }
  | { kind: "rate_limited"; status: 429; message: string; retryAfterSeconds: number }
  // fetch() itself threw — no HTTP response at all (backend unreachable,
  // DNS/network failure). Not part of the original Plan; added per the
  // approved-implementation message's explicit ask.
  | { kind: "network"; message: string }
  | { kind: "unknown"; status: number; body: unknown };

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };
