# Phase 9: Frontend real views
Status: not started
Depends on: Phase 7 (routes), Phase 8 (cache layer — rate limiter and X-Cache both show up in response shapes this phase must handle)
Reads first: docs/CONTRACTS.md §2.2 (API table, status state machine, enums), docs/PARALLEL-WORK-PLAN.md ("Slice: Frontend"), docs/adr/0002-frontend-runtime-config.md, frontend/nginx.conf, frontend/package.json, frontend/src/*

## Goal
Replace the walking-skeleton `Placeholder` page with three real views — Submit, Dashboard, Stats — and a typed API client, each built directly against `docs/CONTRACTS.md`'s API table with zero duplicated backend business rules: the frontend renders what the backend returns or rejects, it never independently decides what's a legal status transition or re-validates what only the backend is allowed to validate.

## Deliverables

**(a) Submit view** (`frontend/src/pages/Submit.tsx`) — consumes `POST /api/complaints` (CONTRACTS.md §2.2: "Validate → triage → persist. 201. 400 with a field-level error body. 429 when the caller exceeds the rate limit."):
- A form for `text`, `location`, `reporter_contact` (optional).
- 201: render the response body as-is — `category`, `priority`, `ai_summary`, `triaged_by` — this is the same call's response, no second request needed to show the triage result.
- 400: render the field-level error body the backend returns, not a client-side re-validation of length/format rules (those limits — 10–2000 chars for `text`, 3–200 for `location` — live in `docs/CONTRACTS.md`'s schema table, i.e. in the backend; the form does not hardcode and pre-reject against them, it submits and shows whatever the backend says).
- 429: read the `Retry-After` header (Phase 8's rate limiter, `docs/specs/phase-08-cache-layer.md`) and render a "try again in Ns" message from it.

**(b) Dashboard view** (`frontend/src/pages/Dashboard.tsx`) — consumes `GET /api/complaints` (filter by category/priority/status, paginate `page`/`page_size` ≤ 100, return `total`) and `PATCH /api/complaints/{id}/status`:
- A paginated list of complaints.
- Per-row status-change actions. Per `PARALLEL-WORK-PLAN.md`'s constraint (no duplicated status-transition table): the UI does **not** precompute which of the four statuses (`open`/`in_progress`/`resolved`/`rejected`) are legal from the row's current status. It always offers all statuses as an action, always sends the `PATCH`, and renders whatever comes back — `200` updates the row in place; `409` renders the backend's rejection body (`current_status`, `attempted_status`) inline next to that row, verbatim. The backend's transition table (`docs/CONTRACTS.md` §2.2) is the only place that decision is made.
- Filtering by category/priority/status needs the dropdown *option lists* for those three enums somewhere in the frontend to render as selectable filters — see Open Question 6 below for exactly what may and may not be duplicated here.

**(c) Stats view** (`frontend/src/pages/Stats.tsx`) — consumes `GET /api/stats` (aggregates, Redis-cached, `X-Cache: HIT|MISS`, `docs/specs/phase-08-cache-layer.md`):
- Renders `counts_by_status`, `average_triage_latency_ms`, and whatever else the response body contains, generically (no hardcoded assumption of exactly N status keys — render the map the backend sends).
- Does **not** surface the `X-Cache` header value in the UI. Checked directly: neither `docs/CONTRACTS.md` nor `docs/RUBRIC-CHECKLIST.md` asks for cache-state to be user-visible; it's an internal freshness mechanism, not a dashboard feature. (Confirmed absent, not assumed absent — see Non-goals.)

**(d) Typed API client** (`frontend/src/api/`) — one module used by all three views:
- Request/response types mirroring `docs/CONTRACTS.md`'s schema (the `Category`/`Priority`/`Status` enums, the complaint shape, the paginated-list envelope, the two error-response shapes — 400's field-level body and 409's `{current_status, attempted_status}` body).
- Thin wrapper functions per endpoint actually consumed by the three views above: `createComplaint`, `listComplaints`, `updateStatus`, `getStats`. `GET /api/complaints/{id}` and `GET /api/meta/providers` are **not** wrapped — see Non-goals.

## Non-goals
- No server-side rendering.
- No auth/login (not in `docs/CONTRACTS.md` — there is no authenticated endpoint anywhere in the API table).
- No surfacing of the `X-Cache` header (Stats view) or `triage_cache_hit_rate` (that field lives on `GET /api/meta/providers`, which no named view consumes — see below) anywhere in the UI. Checked directly against `docs/CONTRACTS.md` and `docs/RUBRIC-CHECKLIST.md`; no requirement found either way, so this is a default-off decision, not an oversight — flag if that reading is wrong.
- No complaint-detail drill-down page and no `GET /api/complaints/{id}` consumption. None of the three named views (`docs/PARALLEL-WORK-PLAN.md`) needs it: Submit shows its own POST response, Dashboard shows list rows with inline actions.
- No `/api/meta/providers` view. Not one of the three named views or an `IMPLEMENTATION-PLAN.md` Phase 9 deliverable; it's an observability surface for provider health, not a citizen/operator-facing view. Revisit if a future phase adds an ops view.
- No hand-copied *decision logic* — the status-transition table stays backend-only, enforced by always attempting every action and rendering the real response (Deliverable b). Enum *value lists* used purely as type/label definitions are addressed separately in Open Question 6, not silently included or excluded here.
- No OpenAPI-codegen build step and no router library added yet — both are named Open Questions below, not preempted.
- No component test framework added yet — same reason (Open Question 4).

## Open Questions

**OQ1 — Routing.** Does a 3-view app need a router library, or is local state enough?
*Recommendation:* no router library. `useState<'submit' | 'dashboard' | 'stats'>` in `App.tsx` (or equivalent) fully covers three flat, non-nested, non-deep-linked views. Nothing in `docs/CONTRACTS.md` or the rubric asks for shareable URLs per view. Adding `react-router` here is a new dependency for a routing problem this app doesn't have. Revisit if a later phase needs deep-linking (e.g. a shareable link to a specific complaint).

**OQ2 — HTTP client.** Native `fetch` vs. adding a library (axios, ky, …)?
*Recommendation:* native `fetch`. Every capability the three views need — GET/POST/PATCH, reading `response.status`, reading the `Retry-After` header — is directly on the Fetch API already available in every target browser and in Vitest's jsdom/happy-dom environment (pending OQ4). No interceptor chain, no cancellation-token complexity, no new dependency justified at this scale.

**OQ3 — Typed API client: hand-typed vs. OpenAPI codegen.** `docs/PARALLEL-WORK-PLAN.md` names both as acceptable ("generated from or hand-typed against the OpenAPI schema").
*Recommendation:* hand-typed. `frontend/src/api/types.ts` written directly against `docs/CONTRACTS.md`'s schema table and cross-checked against the backend's live `/openapi.json` at review time (already available for that check, per Phase 7's "Done looks like" — no new build-time tool needed to read it). A codegen tool (`openapi-typescript`, `orval`, …) is a new dev dependency plus a new build step to keep 9 endpoints' types in sync, 3 of which the frontend even consumes. Revisit if the API surface grows enough that manual sync becomes a real, recurring cost.

**OQ4 — Test framework.** Nothing is pinned in `frontend/package.json` today.
*Recommendation:* Vitest + `@testing-library/react` (+ `@testing-library/user-event`). Vitest shares Vite's own config and module resolution (same maintainer, no separate transform pipeline for ESM the way Jest would need here), and Testing Library is the standard fit for the "component tests" `docs/PARALLEL-WORK-PLAN.md` names as a Frontend-slice deliverable. This is genuinely new dependencies (today there are zero test-related packages) — flagged explicitly for approval, not assumed.

**OQ5 — Data-fetching / loading-state pattern.** Hand-rolled `useState`/`useEffect` vs. a library (React Query, SWR, …), given all three views need loading/error/data state against a small, fixed set of endpoints.
*Recommendation:* a small hand-rolled hook (e.g. `useApiCall`), not a new dependency. React Query/SWR's core value — cache dedup, background refetch, stale-while-revalidate — solves a problem this app doesn't have: 3 views, 4 endpoints, no polling or optimistic-update requirement anywhere in `docs/CONTRACTS.md`. Revisit if the Dashboard later needs live polling.

**OQ6 — Category/Priority/Status enum source for the Dashboard's filter dropdowns.** *(Found during this drafting pass, not one of the five originally asked for — surfacing it rather than silently resolving it either way, per `docs/WORKFLOW.md`.)* `docs/PARALLEL-WORK-PLAN.md` twice states the frontend must not render "a hand-copied category/priority list... as if they were a frontend-owned source of truth." But Deliverable (b)'s filter UI needs *some* concrete list of selectable values before any request returns data — they can't be discovered from a response the user hasn't fetched yet.
*Recommendation:* draw a line between **type/label definitions** (fine) and **decision logic** (not fine). The typed API client (Deliverable d) already has to define `Category`/`Priority`/`Status` as TypeScript union types to type the complaint shape at all — that's schema knowledge mirroring `docs/CONTRACTS.md`, not an invented business rule, and the backend still independently validates every request regardless of what the dropdown offered. What must never be duplicated is *decision* logic — which specific transitions are legal from a given state — and Deliverable (b) already avoids that by never precomputing legal actions (see above). So: the enum value lists may live in `api/types.ts` as passthrough type/label definitions; the transition table may not exist anywhere in the frontend, full stop. Flag if this reading of "duplicated business rule" is too permissive.

## Plan

### Files touched/created, in dependency order

1. **`frontend/package.json`** — new dependencies (exact pins, matching this repo's existing no-range style — `backend/pyproject.toml` pins exact versions, `frontend/package.json` already pins `react`/`react-dom` without `^`):
   - `devDependencies`: `vitest` `5.0.1`, `@testing-library/react` `16.3.3`, `@testing-library/user-event` `14.6.7`, `jsdom` `30.1.1`.
   - New scripts: `"test": "vitest run"` (single-shot, CI-friendly — not the interactive watch mode, matching `verify`-style commands used everywhere else in this project).
   - **`jsdom` is a new dependency not named in OQ4's approval text** — Vitest doesn't bundle a DOM environment; OQ4 approved "Vitest + Testing Library" and jsdom is what makes either of those runnable outside a real browser. Flagging it explicitly here rather than silently adding a fourth package under cover of an already-approved OQ.
   - No `@testing-library/jest-dom`. Not in the approved OQ4 list. Tests will rely on Testing Library's own throwing queries (`getByText`/`getByRole` throw if not found) and plain `expect(x).toBe(y)`/`toEqual(y)` instead of jest-dom's custom matchers (`toBeInTheDocument()` etc.). See "Still uncertain."

2. **`frontend/vite.config.ts`** — one file, not a separate `vitest.config.ts`. Vitest ships `defineConfig` from `"vitest/config"` that re-exports Vite's own `defineConfig` merged with `test`-block typing, so switching the single existing import (`vite` → `vitest/config`) and adding a `test: { environment: "jsdom", globals: false }` block is the whole change — no second config file, no duplicated `plugins: [react()]`.
   - **Environment: `jsdom`, not `happy-dom`.** Both are real options; `happy-dom` is lighter/faster but has known DOM-API gaps (form submission, some layout/CSS behavior) that `@testing-library/react`'s own test suite is written against `jsdom`, not `happy-dom`. At this project's scale (a handful of component test files), jsdom's maturity outweighs happy-dom's marginal speed edge. Standard, not exotic — jsdom is Vitest's own documented default recommendation for React component testing.
   - **`globals: false`**, not Vitest's ambient-global mode. Every test file explicitly imports `describe`/`it`/`expect`/`vi` from `"vitest"`. Matches this project's existing preference for explicit imports over ambient magic (`tsconfig.app.json` already sets `verbatimModuleSyntax: true`, `moduleDetection: "force"` — no implicit globals anywhere else in the frontend either).

3. **`frontend/tsconfig.app.json`** — add `"tests"` to the `include` array (currently `["src"]` only). Without this, `tsc -b`/`tsc -b --noEmit` never typechecks anything under `frontend/tests/`, so `npm run build` and `npm run typecheck` would stay green even if the new test files had type errors — a real gap the current tsconfig has today (it was written for the walking skeleton, which had no tests yet). No `tsconfig.node.json` change needed — `vite.config.ts`'s new `"vitest/config"` import resolves via `node_modules`' own types, not a `types:` array entry.

4. **`frontend/src/api/types.ts`** — hand-typed against `docs/CONTRACTS.md` (OQ3), enum value lists per OQ6's line:
   ```ts
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
     [key: string]: unknown; // rendered generically (Deliverable c) — schema may grow
   }

   export interface ValidationErrorItem { loc: (string | number)[]; msg: string; type: string }

   export type ApiError =
     | { kind: "validation"; status: 400; errors: ValidationErrorItem[] }
     | { kind: "not_found"; status: 404; message: string }
     | { kind: "transition"; status: 409; message: string; currentStatus: Status; attemptedStatus: Status }
     | { kind: "rate_limited"; status: 429; message: string; retryAfterSeconds: number }
     | { kind: "unknown"; status: number; body: unknown };

   export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };
   ```
   `ValidationErrorItem` mirrors FastAPI's own default `RequestValidationError` shape (`backend/app/exception_handlers.py`'s `validation_error_handler`: `{"detail": jsonable_encoder(exc.errors())}` — each item has `loc`/`msg`/`type`), and the 409 shape mirrors `illegal_transition_handler`'s `{"detail": {"message", "current_status", "attempted_status"}}` exactly — both read directly from the actual handler code, not guessed.

5. **`frontend/src/api/client.ts`** — one `request<T>()` helper mapping `fetch`'s response into `ApiResult<T>` by status code (400/404/409/429/else), plus four thin exports: `createComplaint`, `listComplaints`, `updateStatus`, `getStats`. Every call is a relative `fetch("/api/...")` (ADR 0002 — no base URL, ever). `GET /api/complaints/{id}` and `GET /api/meta/providers` are not wrapped (Non-goals).

6. **`frontend/src/hooks/useApiCall.ts`** — the OQ5 hand-rolled hook, shown once, reused by Submit/Stats and by Dashboard's list-fetch:
   ```ts
   type CallState<T> =
     | { status: "idle" }
     | { status: "loading" }
     | { status: "success"; data: T }
     | { status: "error"; error: ApiError };

   function useApiCall<T, Args extends unknown[]>(
     fn: (...args: Args) => Promise<ApiResult<T>>,
   ): [CallState<T>, (...args: Args) => Promise<ApiResult<T>>] {
     const [state, setState] = useState<CallState<T>>({ status: "idle" });
     const run = useCallback(
       async (...args: Args) => {
         setState({ status: "loading" });
         const result = await fn(...args);
         setState(result.ok ? { status: "success", data: result.data } : { status: "error", error: result.error });
         return result;
       },
       [fn],
     );
     return [state, run];
   }
   ```
   **Dashboard's per-row status action does *not* use this hook.** `useApiCall` models exactly one in-flight call at a time; a list of rows can have several actions in flight simultaneously, each needing its own loading/error state keyed by complaint id. Dashboard instead keeps a small local `Record<string, { loading: boolean; error?: ApiError }>` keyed by id and calls `updateStatus` directly. This is a deliberate, disclosed divergence from "the hook's shape shown once, reused by all three views" as originally asked — Submit and Stats (and Dashboard's own list-fetch) do reuse it unchanged; only Dashboard's per-row action doesn't, for the structural reason above.

7. **`frontend/src/pages/Submit.tsx`** — form + `useApiCall(createComplaint)`. Renders, per state: `loading` → disabled submit button; `success` → the 201 body's `category`/`priority`/`ai_summary`/`triaged_by` inline; `error` → branches only on `error.kind` (four fixed cases, not per-field/per-status content):
   - `"validation"` → generic list, `errors.map(e => <li>{String(e.loc.at(-1))}: {e.msg}</li>)`.
   - `"rate_limited"` → `Try again in {retryAfterSeconds}s`.
   - anything else → the raw message, unbranched.

8. **`frontend/src/pages/Dashboard.tsx`** — `useApiCall(listComplaints)` run on mount and whenever page/filters change (a plain `useEffect`, no data-fetching library per OQ5); category/priority/status filter `<select>`s populated from the OQ6-approved value lists in `api/types.ts`; per row, four always-present status-action buttons; a row's 409 renders `Cannot move from {currentStatus} to {attemptedStatus}: {message}` — one generic template, not a per-transition-pair hardcoded message.

9. **`frontend/src/pages/Stats.tsx`** — `useApiCall(getStats)` run on mount; renders `Object.entries(data.counts_by_status)` and `average_triage_latency_ms` generically (Deliverable c already specifies this; restated here only to fix its place in file order).

10. **`frontend/src/App.tsx`** — replaces the `Placeholder` import with the three real views and a `useState<"submit" | "dashboard" | "stats">("submit")` switcher (OQ1) plus three nav buttons.

11. **Delete `frontend/src/pages/Placeholder.tsx`** — fully superseded, no caller left; not left behind as dead code.

12. **`frontend/tests/api-client.test.ts`** — `request()`'s status-code branching, with `global.fetch` stubbed per test (no MSW/nock — no new mocking dependency beyond what OQ4 already approved). Covers all five `ApiError["kind"]` branches, including reading the real `Retry-After` header value into `retryAfterSeconds`.

13. **`frontend/tests/Submit.test.tsx`** — renders `<Submit />`, stubs `fetch`, drives a 201 (result rendered), a 400 (generic list rendered), and a 429 (retry message rendered) through `@testing-library/user-event`.

14. **`frontend/tests/Dashboard.test.tsx`** — renders `<Dashboard />`, stubs `fetch`, asserts a 409 on one row's action renders that row's message without touching any other row's status, and a 200 updates the row in place.

15. **`frontend/tests/Stats.test.tsx`** — renders `<Stats />`, stubs `fetch`, asserts the rendered output reflects an arbitrary `counts_by_status` map (proving it's generic, not hardcoded to today's status set).

### Still uncertain
- No `@testing-library/jest-dom` (see file 1) — if plain-DOM assertions prove too awkward once real tests are written, adding it is a one-line `package.json`/`vite.config.ts` change; not pre-added on spec alone.
- Dashboard's pagination control (prev/next vs. numbered pages) isn't decided — `docs/CONTRACTS.md` only requires `page`/`page_size`/`total` exist, not a specific control shape. Default to prev/next; revisit if a real need for jump-to-page shows up.
- The manual walkthrough (below) runs against the full `docker compose` stack (nginx proxying `/api`, per ADR 0002), not Vite's own dev server (`npm run dev`) — Vite's dev server has no proxy configured today and none is being added in this phase (out of the stated Deliverables). `npm run dev` therefore stays frontend-only/no-backend for now; this matches how every prior phase's manual verification has been done (compose stack up, real browser), not a new gap introduced here.

## Verification required

Automated (real pasted output required in the implementation report, not a claimed pass count — same bar as every prior phase):
```
npm run build
npm run typecheck
npm run lint
npm run test
```

Manual browser walkthrough (`docker compose up -d`, open the frontend's published port, e.g. `http://localhost:8080`):
1. Submit a valid complaint (`text` ≥ 10 chars, `location` ≥ 3 chars). Confirm the 201 response's `category`/`priority`/`ai_summary`/`triaged_by` render inline on the Submit view itself — no second request.
2. Switch to Dashboard. Confirm the just-submitted complaint appears in the list.
3. Switch to Stats. Confirm `counts_by_status` reflects the new complaint (its status's count incremented by 1 vs. before step 1).
4. Submit an intentionally invalid complaint (`text` under 10 chars). Confirm the 400 response's field-level errors render as a generic list, not a blank/generic "something went wrong."
5. From the Submit view, submit `settings.rate_limit_max` times in quick succession, then once more. Confirm the final submission renders the 429 message using the response's actual `Retry-After` value (not a hardcoded number).
6. On Dashboard, attempt an illegal transition (e.g. click "resolved" on a row still `open`, skipping `in_progress`). Confirm the 409 rejection renders inline next to that row (naming `current_status`/`attempted_status`) and the row's displayed status does not change.
7. On Dashboard, perform a legal transition on the same or another row (e.g. `open` → `in_progress`). Confirm 200 and the row updates in place, and that step 6's row (still showing its 409) was unaffected by this action.

## Ambiguity handling
Open Question 6 above is exactly this section in practice: a real ambiguity between two directly-stated constraints (need concrete filter options vs. no hand-copied enum lists) that isn't resolved by silent assumption — surfaced for a decision instead.

## As-Built
(Empty — this phase has not been implemented.)
