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

Everything below was actually run — not guessed — against an isolated scratch copy of `frontend/`'s config (`package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `eslint.config.js`, `src/`) outside this repo, specifically so real CLI/dependency behavior could be confirmed before committing to it here. Three real surprises came out of that, each documented where it applies below rather than glossed over.

### Files touched, in dependency order

1. **`frontend/tsconfig.json`** (root) — add:
   ```json
   "compilerOptions": {
     "paths": { "@/*": ["./src/*"] }
   }
   ```
   **No `baseUrl`.** Tried first with `"baseUrl": "."` (the form shadcn's own docs show) and got a real `tsc -b` error: `TS5101: Option 'baseUrl' is deprecated and will stop functioning in TypeScript 7.0`, against this project's actual pinned `typescript@6.0.3`. Modern TS resolves `paths` without `baseUrl` (relative to the config file's own directory) — confirmed by removing it and re-running `tsc -b --noEmit` clean in the scratch copy.
   **Why the root file, not just `tsconfig.app.json`:** reproduced a real shadcn CLI bug first — `npx shadcn@latest add input` against a scratch copy with the alias only in `tsconfig.app.json` (this project's existing split-config shape, `tsconfig.json` → references → `tsconfig.app.json`/`tsconfig.node.json`) silently wrote `./@/components/ui/input.tsx` at the project root instead of `./src/components/ui/input.tsx` — no error, just wrong output. Root cause, confirmed via [cubicecho/cubeui#54](https://github.com/cubicecho/cubeui/issues/54): the shadcn CLI only reads the root `tsconfig.json` to validate/resolve the alias, and Vite's own template convention keeps `paths` in `tsconfig.app.json` instead — a real, known mismatch, not something specific to this project's config. Adding the same `paths` block to the root file fixed it; re-ran `add` in the scratch copy and got the correct `src/components/ui/*` location.

2. **`frontend/tsconfig.app.json`** — same `paths` addition (no `baseUrl` here either, same reasoning). `include` already covers `src`/`tests` from Phase 9; nothing else changes here.

3. **`frontend/vite.config.ts`**:
   ```ts
   import path from "node:path";

   import tailwindcss from "@tailwindcss/vite";
   import react from "@vitejs/plugin-react";
   import { defineConfig } from "vitest/config";

   export default defineConfig({
     plugins: [react(), tailwindcss()],
     resolve: {
       alias: {
         "@": path.resolve(import.meta.dirname, "./src"),
       },
     },
     test: {
       environment: "jsdom",
       globals: false,
     },
   });
   ```
   **`import.meta.dirname`, not `__dirname`.** Tried `__dirname` first (the form most existing tutorials show); a real `vite build` against this project's pinned `vite@8.3.0` printed: `Your Vite config uses features that are unsupported by 'configLoader: native'... - __dirname ... Use import.meta.dirname instead`. Switched and rebuilt clean, warning gone. `test`/`plugins: [react()]` block is Phase 9's existing config, untouched aside from the addition.

4. **`frontend/package.json`** — new `dependencies` (this repo's convention pins runtime-shipped packages under `dependencies`, not `devDependencies`; all six below end up in the built bundle, unlike Phase 9's test tooling). Exact versions below are what actually got installed into the scratch copy today (2026-09-24), pins stripped of the `^` `npm install` adds by default — this repo has no `.npmrc`/`save-exact` setting (checked directly), so every prior phase's exact-pin style has been hand-applied the same way, not tool-enforced:
   - `@tailwindcss/vite` `4.3.3`, `tailwindcss` `4.3.3` — OQ1.
   - `class-variance-authority` `0.7.1` — the `cva()` helper all four shadcn components use for their `variant` props.
   - `cn` `0.4.0` — what the current shadcn CLI scaffolds `src/lib/utils.ts` to re-export (`export { cn } from "cn"`), described by its own `package.json` as "a fast, small, compiled class-name merging for Tailwind CSS. Drop-in replacement for clsx + tailwind-merge." One dependency, not two (`clsx` + `tailwind-merge` separately, as the Open Questions stage assumed before the CLI was actually run) — kept as scaffolded rather than hand-rolling an equivalent.
   - `radix-ui` `1.6.7` — the current CLI's single unified Radix package (superseding the older per-primitive `@radix-ui/react-slot` etc. naming the Open Questions stage assumed). Only used for `Slot.Root`, which `Button`/`Badge` use for `asChild` support.
   - `lucide-react` `1.48.0` — **not used by anything in this phase's own code.** It's installed unconditionally by the CLI because `components.json`'s `iconLibrary` defaults to `"lucide"`, regardless of whether any scaffolded component actually imports an icon (confirmed: none of Button/Input/Textarea/Badge's real source references it). Disclosed rather than silently kept or fought — removing it would mean overriding CLI-managed config for a small, inert dependency; not worth it. The header's own EKG icon stays a hand-authored inline `<svg>`, per the original ask, not a `lucide-react` icon.
   - **Deliberately not added**, despite being what a default `shadcn init` run pulls in (see step 6): `@fontsource-variable/geist` (a self-hosted font package — the brief specifies IBM Plex via Google Fonts `<link>`, not a bundled font), `tw-animate-css` (grep-confirmed: none of the four scaffolded components use any `animate-*`/`fade-*` class), `shadcn` itself as a **runtime** dependency (only needed if `src/index.css` keeps the preset's own `@import "shadcn/tailwind.css"`, which step 6 replaces).

5. **`frontend/index.html`** — Google Fonts, in `<head>`:
   ```html
   <link rel="preconnect" href="https://fonts.googleapis.com" />
   <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
   <link
     href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
     rel="stylesheet"
   />
   ```
   (`frontend/nginx.conf`, checked directly again at Plan time, still sets no CSP header — nothing to loosen for these two Google-owned hosts.)

6. **Run `npx shadcn@latest init --template vite --base radix --preset nova --yes --cwd frontend`** (only after steps 1–5 land, since the CLI's own preflight checks require Tailwind and the alias to already resolve — confirmed directly: run before those, it fails outright with "No Tailwind CSS configuration found" / "Could not find valid path aliases"). This is `shadcn@4.21.0` (resolved just now) — a materially different CLI from the older `shadcn-ui` package most existing tutorials describe: it has template/base/preset flags instead of the old interactive-only prompts, and no non-preset ("bare") non-interactive path exists — every `init` run scaffolds a full opinionated preset (font package, animation utility package, its own base CSS layer) whether or not you want that preset's visual identity. Rather than fight the CLI's flag surface trying to avoid ever touching Nova's scaffold, the plan is: run it for real, then edit its output down, in this order:
   - Creates `frontend/components.json`, `frontend/src/lib/utils.ts` (the one-line `cn` re-export), `frontend/src/components/ui/button.tsx`, and overwrites `frontend/src/index.css` with Nova's own theme.
   - **`components.json` is kept as generated**, including `"style": "radix-nova"` — that field is CLI bookkeeping for which registry variant to fetch on a future `add`, not something rendered; renaming it risks breaking `add` for no visual benefit, since step 7 replaces the actual token values regardless of the label.

7. **`frontend/src/index.css`** — replace Nova's generated content wholesale with the design brief's own tokens (verified: `tsc -b --noEmit` and `vite build` both pass clean against this exact block in the scratch copy):
   ```css
   @import "tailwindcss";

   :root {
     --background: #ffffff;
     --surface: #f4f3f1;
     --border: #dddad3;
     --ink: #1a1a18;
     --ink-secondary: #55534c;
     --ink-muted: #8b887f;
     --brand: #0e6379;
     --emblem: #e8a33d;

     --status-open: #2e4a73;
     --status-in_progress: #8a5a1e;
     --status-resolved: #29694a;
     --status-rejected: #6b685f;
     --priority-high: #a13a31;
     --priority-normal: #6b685f;
     --priority-low: #2e4a73;
   }

   @media (prefers-color-scheme: dark) {
     :root {
       --background: #171613;
       --surface: #201f1b;
       --border: #38352d;
       --ink: #efede7;
       --ink-secondary: #c7c4bb;
       --ink-muted: #9a968c;
       --brand: #0a3540;
       --emblem: #e8a33d;

       --status-open: #6c8fc9;
       --status-in_progress: #d9a054;
       --status-resolved: #5fae81;
       --status-rejected: #a6a296;
       --priority-high: #d97a70;
       --priority-normal: #a6a296;
       --priority-low: #6c8fc9;
     }
   }

   @theme inline {
     --font-sans: "IBM Plex Sans", sans-serif;
     --font-mono: "IBM Plex Mono", monospace;

     --color-background: var(--background);
     --color-foreground: var(--ink);
     --color-card: var(--background);
     --color-card-foreground: var(--ink);
     --color-popover: var(--background);
     --color-popover-foreground: var(--ink);
     --color-primary: var(--brand);
     --color-primary-foreground: #ffffff;
     --color-secondary: var(--surface);
     --color-secondary-foreground: var(--ink);
     --color-muted: var(--surface);
     --color-muted-foreground: var(--ink-secondary);
     --color-accent: var(--surface);
     --color-accent-foreground: var(--ink);
     --color-destructive: var(--priority-high);
     --color-border: var(--border);
     --color-input: var(--border);
     --color-ring: var(--brand);

     --color-emblem: var(--emblem);
     --color-ink-muted: var(--ink-muted);
     --color-status-open: var(--status-open);
     --color-status-in_progress: var(--status-in_progress);
     --color-status-resolved: var(--status-resolved);
     --color-status-rejected: var(--status-rejected);
     --color-priority-high: var(--priority-high);
     --color-priority-normal: var(--priority-normal);
     --color-priority-low: var(--priority-low);

     --radius-sm: 0.125rem;
     --radius-md: 0.375rem;
     --radius-lg: 0.5rem;
   }

   @layer base {
     * {
       @apply border-border outline-ring/50;
     }
     body {
       @apply bg-background text-foreground font-sans;
     }
   }
   ```
   Notes on this exact mapping:
   - **Dark mode via `@media (prefers-color-scheme: dark)`, not a `.dark` class.** Nova's own generated CSS used `@custom-variant dark (&:is(.dark *));` plus a `.dark { ... }` block — i.e. the CLI's own default assumes a manually-toggled class. That's discarded here, not carried over, per OQ5's already-approved decision (media-query only, no toggle).
   - `--destructive` is mapped to `--priority-high` (red) — the closest existing hue to a "danger" semantic in the brief; nothing in the four scaffolded components needs a *separate* destructive color from priority-high today, so no new token was invented for it.
   - `--input` reuses `--border` — the brief gives one border color, not a separate input-border color; not inventing a second one.
   - Seven status/priority tokens are kept **distinct even though two pairs share an identical hex** in the brief itself (`--status-open` / `--priority-low` both `#2e4a73`; `--status-rejected` / `--priority-normal` both `#6b685f`, in both light and dark) — each caller (Badge, keyed by the exact `Status`/`Priority` string) reads its own named token rather than a shared one, so the two concepts can diverge later without a rename; the coincidence is the brief's, not manufactured here.
   - Radius scale is deliberately small (`sm`/`md`/`lg` only) — the brief only ever asks for one exact radius (tags, 2px = `--radius-sm`); `md`/`lg` are reasonable defaults for Button/Input/Textarea/the header badge circle, not independently specified, so not overthought.

8. **`frontend/package.json`, second edit** — remove `@fontsource-variable/geist`, `tw-animate-css`, `shadcn` (added by step 6's `init`, made unnecessary by step 7's replacement), then reinstall so the lockfile matches.

9. **Run `npx shadcn@latest add input textarea badge --yes --cwd frontend`** (Button already exists from step 6). Confirmed in the scratch copy: with steps 1–3 in place, this correctly writes `src/components/ui/{input,textarea,badge}.tsx` — no new dependencies beyond step 4's (`Input`/`Textarea` are radix-free; `Badge` reuses the same `radix-ui`/`class-variance-authority`/`cn` already installed).

10. **`frontend/src/components/ui/badge.tsx`** — hand-edit after scaffolding (shadcn components are meant to be owned/edited post-generation, same model Phase 9's Non-goals already assumed for the typed API client vs. codegen). Replace the generated `variant` union (`default`/`secondary`/`destructive`/`outline`/`ghost`/`link` — none of which map to this app's domain) with the seven values that are the actual `Status`/`Priority` unions themselves (`open`/`in_progress`/`resolved`/`rejected`/`high`/`normal`/`low`), each variant's class string reading its matching `--color-status-*`/`--color-priority-*` token from step 7, plus `rounded-sm` (2px, the brief's explicit ask — overriding the generated `rounded-4xl` pill shape), `uppercase`, and `text-white`. `cva`'s existing `variant`-keyed structure already fits this without restructuring the component, just relabeling the variant keys and their class strings.

11. **`frontend/src/components/Header.tsx`** (new, extracted rather than left inline in `App.tsx` — a 4-item nav plus a brand band plus an icon is enough markup to earn its own file) — solid brand-color (`bg-primary`) band; a small white circle (`bg-white rounded-full`) containing one hand-authored inline `<svg>` (a simple 3–4 point EKG zigzag `<path>`, `stroke` set to `var(--brand)`); the "CivicPulse" wordmark in white text; a `<nav>` of four shadcn `Button`s (`variant="ghost"`), one per view, each taking `view`/`onNavigate` props from `App.tsx` (same lifting-state-up shape `App.tsx` already uses, no new state elsewhere) — the active one gets a `border-b-2` in `emblem` color.

12. **`frontend/src/components/Footer.tsx`** (new) — one row: a copyright/non-emergency line, plus three `<span>`s ("Accessibility", "Privacy", "Contact") — not `<a>`, per Non-goals (no destination pages approved yet).

13. **`frontend/src/api/types.ts`** — relocate, don't duplicate: `Dashboard.tsx` already defines `CATEGORIES`/`PRIORITIES`/`STATUSES` as local `const` arrays typed against the `Category`/`Priority`/`Status` unions this file exports. Home's categories sentence (Deliverable d) needs the same `CATEGORIES` list — rather than a second hand-copied literal array (exactly the kind of duplication OQ6 in Phase 9's own spec already flagged as not fine), these three arrays move here, exported alongside the types they enumerate. **Not itemized in the original spec's Deliverables** — flagging it as a small, disclosed addition to this Plan rather than silently doing it or silently duplicating instead.

14. **`frontend/src/pages/Home.tsx`** (new) — hero (headline/lede/an `onNavigate("submit")`-wired `Button`), one hand-authored decorative inline skyline `<svg>` (low-opacity, `fill` in `var(--brand)`, no image asset/pipeline), the 3-stat row via `useApiCall(getStats)` (a second call site of Phase 9's existing hook/client — not a new one), the categories sentence built from `CATEGORIES` (step 13), the "How it works" 3-step static section (numbered circle badges, no data dependency).

15. **`frontend/src/pages/Submit.tsx` / `Dashboard.tsx` / `Stats.tsx`** — restyle only. Swap raw `<button>`/`<input>`/`<textarea>` for `@/components/ui/{button,input,textarea}`; swap Dashboard's plain-text status cell and a new priority cell for the edited `Badge` (`variant={complaint.status}` / `variant={complaint.priority}`); move Submit's non-emergency disclaimer text in (Deliverable e). Every `state.status`/`error.kind` branch, every `data-testid="status"`, every button's visible text (`"Submit"`, `"resolved"`, etc.), and every label association stays byte-identical — OQ3's condition for the existing tests surviving.

16. **`frontend/src/App.tsx`** — `View` becomes `"home" | "submit" | "dashboard" | "stats"`, default `"home"` (not `"submit"` as Phase 9 had it — once a Home view exists at all, it's the natural landing view; disclosed as a real, deliberate behavior change, not an oversight). Renders `<Header>`/`<Footer>` around the switched page content, passing `view`/`setView` down to `Header`.

17. **`frontend/tests/Home.test.tsx`** (new) — **not named in the original spec's Deliverables or Verification required**, added here because Home is genuinely new page logic (a live stat-row fetch, a nav action), not a restyle of already-tested logic the way Submit/Dashboard/Stats are — OQ3's "existing tests survive a restyle" reasoning doesn't cover code that didn't exist before. Two cases: the stat row renders a mocked `getStats` response's real values (same stubbed-`fetch` pattern as `Stats.test.tsx`), and clicking "Report an issue" calls the `onNavigate` prop with `"submit"`.

### Still uncertain
- **`react-refresh/only-export-components` ESLint warnings on the CLI's own `button.tsx`/`badge.tsx`** (each file exports both a component and its `cva` variants function) — reproduced directly in the scratch copy: 2 warnings, 0 errors, `eslint .` still exits `0` (this project's `lint` script has no `--max-warnings` gate). Left as-is rather than restructured into extra files — restructuring shadcn's own generated component shape isn't this phase's job, and the warning is inert. Flagging now so `npm run lint`'s real output at implementation time (2 warnings) isn't mistaken for a new problem introduced by this phase's own code, unlike Phase 9's fully-silent `lint` output.
- **`Home.test.tsx` (file 17) is a recommended addition, not something you asked for by name** — surfaced rather than silently added or silently skipped.
- Exact skyline/EKG SVG path data isn't drafted here — simple enough to write directly at implementation time, not worth pre-specifying path coordinates in a Plan.

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
