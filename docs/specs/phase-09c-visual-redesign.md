# Phase 09c: Visual redesign
Status: not started
Depends on: Phase 9 (frontend real views) — done (`f739d2a`, `498642c`, `c19d85d`, `326e0dd`, `969ef79`, `a6c716d`, `7398903`). This is new scope beyond `docs/IMPLEMENTATION-PLAN.md`'s original Phase 9 entry, not a correction to it — Phase 9's own three views and typed API client are closed and are being restyled, not rebuilt.
Reads first: `docs/specs/phase-09-frontend-views.md` (Plan + As-Built), `frontend/src/*` as it exists after Phase 9 (`App.tsx`, `api/client.ts`, `api/types.ts`, `hooks/useApiCall.ts`, `pages/Submit.tsx`, `Dashboard.tsx`, `Stats.tsx`), `frontend/tests/*`, `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.app.json`, `frontend/nginx.conf`, `docs/PARALLEL-WORK-PLAN.md`'s "Slice: Frontend" section, `docs/adr/0002-frontend-runtime-config.md`.

## Goal
Restyle the existing Submit/Dashboard/Stats views and add one new Home view to a specific approved visual design (typography, color tokens, header/footer shape, tag styling, copy discipline), wiring up Tailwind CSS and shadcn/ui as the mechanism — without changing any data-fetching, API-client, or business-rule behavior Phase 9 already built and verified.

## Deliverables

**(a) Design-system foundation**
- Tailwind CSS wired into `frontend/vite.config.ts` via `@tailwindcss/vite` (Tailwind v4's own Vite plugin — no separate PostCSS config file needed, see Open Question 1).
- One new `frontend/src/index.css`: `@import "tailwindcss";` plus a `@theme` block defining the design brief's color tokens (background/surface/border/ink/brand/emblem-accent, status-tag colors, priority-tag colors) for light mode, and the dark-mode equivalents scoped correctly for Tailwind v4's default `prefers-color-scheme`-based `dark:` variant (see Open Question 5).
- IBM Plex Sans (400/500/600/700) + IBM Plex Mono (400/500/600) loaded via Google Fonts `<link>` tags in `frontend/index.html` (`nginx.conf`, checked directly, sets no Content-Security-Policy header, so nothing needs loosening for `fonts.googleapis.com`/`fonts.gstatic.com` to load).

**(b) shadcn/ui setup**
- `frontend/components.json`, a `@/*` path alias added to both `frontend/tsconfig.app.json` (`paths`) and `frontend/vite.config.ts` (`resolve.alias`), and `frontend/src/lib/utils.ts` (the standard `cn()` helper shadcn's CLI scaffolds).
- Only the components named in Open Question 2's per-component recommendation get scaffolded — not the full shadcn set reflexively.

**(c) Header** (new, lives in `App.tsx` or a small extracted `Header` component)
- Solid brand-color band containing: a small circular white badge with an inline hand-authored EKG/pulse-line SVG icon (no icon library — one bespoke icon doesn't justify a new dependency), the "CivicPulse" wordmark, and a 4-item top nav (Home / Report an issue / Dashboard / Stats) with an emblem-accent-colored underline on the active item.

**(d) Home view (new)** (`frontend/src/pages/Home.tsx`)
- Hero: headline + lede + a "Report an issue" button that switches `App.tsx`'s view state to Submit, plus a faint decorative skyline-silhouette SVG.
- A 3-stat row reading real data from `GET /api/stats` — reuses the existing `getStats`/`useApiCall` exactly as `Stats.tsx` already does, no new endpoint, no hardcoded numbers.
- A plain-sentence paragraph naming the six reportable categories (`water`/`electricity`/`sanitation`/`roads`/`streetlights`/`other` — the same `Category` union already in `api/types.ts`, not a re-typed list; see Open Question 6 in Phase 9's own spec, which this reuses rather than reopens).
- A "How it works" section, 3 numbered-badge steps.

**(e) Restyle Submit / Dashboard / Stats** (`frontend/src/pages/Submit.tsx`, `Dashboard.tsx`, `Stats.tsx`)
- Same component structure, same `useApiCall`/`api/client.ts` calls, same conditional branches on `state.status`/`error.kind` — markup and class names only change.
- Status and priority values render as small flat solid-fill tags (rounded 2px, uppercase via CSS `text-transform`, white text) using the shadcn Badge component (Open Question 2), keyed to the design brief's per-value colors.
- The non-emergency disclaimer becomes a plain text line inside `Submit.tsx` only — not a persistent site-wide banner.

**(f) Footer** (new) — one plain row: a copyright/non-emergency-affiliation line + 3 plain text links (Accessibility, Privacy, Contact). These 3 links have no destination pages in scope (see Non-goals) — they render as inert `<span>`/non-navigating elements, not broken `<a href="#">`s, unless a real target is approved.

**(g) Copy discipline** — applied while restyling (c)–(f): no ALL-CAPS eyebrow labels, no middle-dot-joined meta strings, no spaced-em-dash headlines, no arrows on button text.

## Non-goals
- No new backend endpoint, no map, no file upload, no login. Confirmed: exactly the same 4 endpoints Phase 9 already consumes (`createComplaint`, `listComplaints`, `updateStatus`, `getStats`) — Home's stat row is a second call site for `getStats`, not a new one.
- No SSR, no i18n, no complaint-detail drill-down page (unchanged from Phase 9's own Non-goals — this phase doesn't reopen them).
- No real destination pages for the footer's Accessibility/Privacy/Contact links — out of scope until content for them is approved.
- No manual dark-mode toggle control — see Open Question 5.
- The existing typed API client (`api/client.ts`, `api/types.ts`) and `useApiCall` hook are **not being replaced**. Nothing in this phase changes `request()`'s branching, `ApiError`'s variants, or the hook's shape — restyling is presentation-layer only, on top of the exact data layer Phase 9 built.

## Open Questions

**OQ1 — How Tailwind gets wired into the existing Vite config.**
The premise in the original ask (avoiding conflict with "the hand-written CSS Phase 9 already shipped") doesn't hold: checked directly, Phase 9 shipped **zero CSS** — no `.css` file anywhere in `frontend/src`, no `<style>` in `frontend/index.html`, no CSS import in `main.tsx`. Every element today renders with the browser's unstyled defaults. So this isn't "full replacement vs. incremental adoption of existing styles" — it's adopting Tailwind onto a blank slate.
*Recommendation:* full adoption via Tailwind v4's `@tailwindcss/vite` plugin (confirmed current version `4.3.3` via `npm view`, alongside `tailwindcss@4.3.3`) added to `vite.config.ts`'s `plugins` array, plus one `src/index.css` importing Tailwind and defining the design brief's tokens in a `@theme` block — Tailwind v4's own CSS-first config mechanism, no separate `tailwind.config.js`/PostCSS config file needed. Since there's no legacy CSS to reconcile, there's no partial-adoption question to answer.

**OQ2 — Which shadcn/ui components are actually needed.**
*Recommendation, per component named as an "obvious candidate":*
- **Button** — yes. Used across nav, Home's CTA, Submit's submit button, Dashboard's 4 per-row status actions; real value from a shared disabled/loading-state style instead of repeating utility classes at every call site.
- **Input** — yes. Submit's `location`/`reporter_contact` fields; a real, reused component, not a one-off.
- **Textarea** — yes. Submit's `text` field; same reasoning.
- **Select** — **no.** Dashboard's 3 filter dropdowns are plain, single-select, no search/multi-select/async-option behavior — everything a native `<select>` already does. shadcn's Select wraps `@radix-ui/react-select`, a real dependency pulled in for functionality this app doesn't use beyond what's native. Recommendation: plain `<select>` + Tailwind utility classes, not the shadcn component.
- **Badge** — yes. Status/priority tags appear in multiple places (Dashboard rows, potentially Home) with a fixed small set of color variants (4 status + 3 priority) — a single `variant`-keyed component avoids repeating the same color-mapping logic at each render site, which is exactly what a shared component earns its keep on.
- Net new runtime-ish dependencies this implies (only `Button`'s `asChild` support needs `@radix-ui/react-slot`; `Input`/`Textarea`/`Badge` are radix-free): `class-variance-authority`, `clsx`, `tailwind-merge`, `@radix-ui/react-slot`. Exact versions to be pinned at Plan time, after actually running `npx shadcn@latest init`/`add` and reading what it scaffolds — not guessed now.

**OQ3 — Do Phase 9's existing tests survive a pure restyle?**
Checked directly against the four existing test files (`frontend/tests/{api-client,Submit,Dashboard,Stats}.test.tsx`):
- `api-client.test.ts` tests `client.ts` directly with no DOM at all — completely unaffected by any styling change, regardless of outcome elsewhere.
- `Submit.test.tsx`/`Dashboard.test.tsx`/`Stats.test.tsx` query exclusively by accessible role/name (`getByRole("button", { name: ... })`), label text (`getByLabelText(/text/i)`), literal rendered text (`getByText(/Category: roads/)`, `/Cannot move from open to resolved/`, `/Data: cached/`), and one `data-testid="status"`.
*Recommendation:* yes, they were written robustly enough to survive a pure restyle, **conditional on** the restyle preserving: each form field's label-to-input association (`<label>` wrapping or `htmlFor`/`id`, whether via shadcn's `Label` or plain `<label>`), every button's accessible name (visible text unchanged — e.g. Dashboard's `resolved` button must still be named exactly `"resolved"`, not replaced with an icon), every literal string these tests assert on, and the `data-testid="status"` attribute on Dashboard's status cell. `text-transform: uppercase` (a CSS-only presentation change) does not change a DOM node's actual text content, so it doesn't break these text-content assertions. This is a testable claim, not an assumption — `npm run test` after the restyle is part of Verification required below, and any test that breaks gets fixed for real (updated to match a genuinely changed accessible name/structure) rather than the recommendation being treated as proof on its own.

**OQ4 — Does Phase 9's OQ1 (no router) still hold with 4 views instead of 3?**
*Recommendation:* yes, unchanged. Home joins Submit/Dashboard/Stats as a fourth flat, non-nested, peer view — the design brief's nav lists exactly 4 items, all switched via the same mechanism, none needing its own URL, deep link, or browser-history entry. Nothing in `docs/CONTRACTS.md` or the rubric newly asks for shareable per-view URLs just because a 4th view exists. `App.tsx`'s `useState<View>` (extended to a 4-member union) still fully covers this; adding `react-router` for a routing need that still doesn't exist would be an unjustified new dependency at this scale, same reasoning as Phase 9's original OQ1.

**OQ5 — Dark-mode activation mechanism.** *(Found during this drafting pass — the design brief specifies full dark-mode token values but never describes a toggle control anywhere in the header/footer/nav element list it does describe, so this is a real gap, not a silently resolved one.)*
*Recommendation:* OS-preference-only, via `prefers-color-scheme` — which is Tailwind v4's own default behavior for the `dark:` variant with zero extra configuration (no `@custom-variant dark (&:where(.dark, .dark *))` override needed, no toggle state, no `localStorage` persistence code). Adding a manual toggle would be inventing a UI control the brief never asks for. Revisit if a manual toggle is explicitly wanted later.

## Plan
Not filled in yet — pending your decisions on Open Questions 1–5 above, same two-step process as Phase 9's own spec (draft → decide Open Questions → Plan → approval → implement).

## Verification required
Automated (real pasted output required in the implementation report, same bar as every prior phase):
```
npm run build
npm run typecheck
npm run lint
npm run test
```
Manual browser walkthrough:
1. Home view's 3-stat row matches a direct `GET /api/stats` check performed at the same moment (proving it's real data, not hardcoded).
2. Nav between all 4 views (Home, Report an issue, Dashboard, Stats) — active-item underline moves correctly.
3. Phase 9's own manual walkthrough (submit/dashboard/stats/429/409, `docs/specs/phase-09-frontend-views.md`'s Verification required, steps 1–7) still passes end-to-end with the new styling — same behaviors, new appearance only.

## Ambiguity handling
Open Questions 1 and 5 above are both real corrections/gaps found against the original ask (no existing CSS to reconcile with; no stated dark-mode toggle mechanism) — surfaced here rather than silently resolved either way, per `docs/WORKFLOW.md`.

## As-Built
Not started.
