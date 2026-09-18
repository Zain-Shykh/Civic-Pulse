# ADR 0002: Frontend runtime configuration — nginx `/api` proxy

## Status

Accepted

## Context

Vite bakes `import.meta.env` values into static JS at build time (§2.1). If the backend's URL is baked in, the frontend image becomes environment-specific, breaking build-once-deploy-many — one of the automatic-deduction-adjacent failure modes the spec calls out by name as "the part most students get wrong." The spec names exactly two acceptable fixes and requires an ADR picking one:

1. Serve `/config.js`, generated from environment variables at container start, that the frontend fetches and reads the backend URL from.
2. Proxy `/api` through nginx, so the frontend never needs an absolute backend URL at all.

## Decision

**Proxy `/api` through nginx.** The frontend's built JS makes relative requests to `/api/...` and `/health`-style paths; nginx (already serving the static build, per §2.1's multi-stage image) forwards those to the backend service via a plain `location /api/ { proxy_pass http://backend:8000; }` block (exact upstream host/port to be finalized against the actual Compose/K8s service names in later phases — this ADR fixes the mechanism, not that value).

This means:
- The frontend's own JavaScript contains no host, port, or protocol for the backend — not in the build, not in an env var, not anywhere. There's nothing to leak and nothing to bake in.
- The same built image runs unmodified in Docker Compose (`backend` service name), Kubernetes (Ingress + Service), or any other environment where nginx's config is adjusted at deploy time — which is itself just an nginx config file, not application code.
- No container-start scripting is needed on the frontend side (no entrypoint script templating a JS file from env vars, no risk of that script failing silently and leaving a stale/missing `/config.js`).

## Consequences

- nginx's config becomes the one place that knows the backend's address, and that config differs (correctly) between Compose and Kubernetes — this is configuration, not code, and is exactly the kind of environment-specific detail that's supposed to live outside the image.
- CORS stops being a concern for the browser-facing API calls at all — same-origin requests to `/api/...` never trigger a CORS preflight, since the browser only ever talks to the origin serving the page. (CORS may still matter for direct backend access during local backend-only development, but that's a development convenience, not a production path.)
- If a future requirement needs the frontend to read *non-backend-URL* runtime config (e.g. a feature flag, an analytics key), the `/config.js` pattern would need to be introduced anyway for that value — this decision doesn't preclude adding it later for a different purpose, it just avoids using it for the one purpose (the backend URL) that doesn't need it.

## Alternatives considered

- **`/config.js` generated at container start:** Also satisfies the no-baked-URL requirement, and is the more general mechanism (works for any runtime value, not just a same-origin API path). Rejected as the primary mechanism here because it's strictly more moving parts for this specific need — a container-start script, `envsubst` or equivalent templating, and a new failure mode (the script not running, or running before env vars are populated) — to solve a problem the nginx proxy solves with a static two-line config block and zero runtime scripting. Ladder logic: prefer the native platform feature (nginx, already present) over adding a generation step.
