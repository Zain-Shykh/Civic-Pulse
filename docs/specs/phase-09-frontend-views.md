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
(Left empty — filled in and committed separately, after these Open Questions are decided.)

## Verification required
(To be finalized once the Plan is written, but at minimum, per `docs/IMPLEMENTATION-PLAN.md`'s Phase 9 "Done looks like": `npm run build`, `npm run typecheck`, `npm run lint` all green; whatever test command OQ4 lands on, green; and a manual browser walkthrough — submit a complaint and see it appear on the Dashboard, see Stats update, drive `POST /api/complaints` past the rate limit and see the Submit view's 429 handling, and trigger an illegal transition on the Dashboard and see the 409 rejection rendered.)

## Ambiguity handling
Open Question 6 above is exactly this section in practice: a real ambiguity between two directly-stated constraints (need concrete filter options vs. no hand-copied enum lists) that isn't resolved by silent assumption — surfaced for a decision instead.

## As-Built
(Empty — this phase has not been implemented.)
