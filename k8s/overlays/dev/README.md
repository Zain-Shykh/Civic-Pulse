Dev overlay on top of k8s/base.

Uses the base ConfigMap's default `TRIAGE_PROVIDER=rules` (no Gemini key
needed) and the base Secret's placeholder values as-is — this overlay is
for local smoke-testing, not a real deploy.

## Bring it up on k3d

```
k3d cluster create civicpulse
docker build -t civicpulse-backend:dev backend/
docker build -t civicpulse-frontend:dev frontend/
k3d image import civicpulse-backend:dev civicpulse-frontend:dev -c civicpulse
kubectl apply -k k8s/overlays/dev
kubectl get pods -n civicpulse -w
```

## Reach it

Add to `/etc/hosts`:

```
127.0.0.1 civicpulse.local
```

Then `curl http://civicpulse.local/` (frontend) and
`curl http://civicpulse.local/api/stats` (backend, via Traefik, k3d's
bundled ingress controller).

## Tear down

```
kubectl delete -k k8s/overlays/dev
```
