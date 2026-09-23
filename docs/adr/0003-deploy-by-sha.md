# ADR 0003: Deploy by immutable commit SHA

## Status

Accepted

## Context

The assignment is explicit and unforgiving on this point (§3.4, §5.3): `:latest` may be pushed but must never be deployed (−8 automatic deduction if it is), every publishing/deploying job must be gated by `needs:` (−8 if not), and "what is production running?" must have a one-word answer pasteable into `git show`. `cd.yml` (on push to `main`) builds both images, pushes to GHCR tagged `${{ github.sha }}` and `latest`, and a later job deploys `overlays/prod` to an ephemeral k3d cluster.

## Decision

The commit SHA is the only tag ever referenced by a deployment. The flow:

1. **`test` job** runs the full suite on the merged result. Nothing downstream runs without this passing.
2. **`build-push` job** (`needs: test`) builds both images, pushes to GHCR as `ghcr.io/<org>/<image>:${{ github.sha }}` and `:latest`. The SHA tag is the deployable artifact; `:latest` is published purely as a convenience pointer for humans browsing GHCR, and is never referenced by any manifest or `kubectl` command. This job's output includes the image digest (per §3.4's "capture the image digest as a job output" — the digest is captured now even though tag-based SHA deploy, not digest-pinning, is the baseline; digest-pinning is the bonus upgrade path, see Alternatives).
3. **`deploy-k8s` job** (`needs: build-push`) does not edit any committed YAML. It runs `kustomize edit set image backend=ghcr.io/<org>/backend:${{ github.sha }} frontend=ghcr.io/<org>/frontend:${{ github.sha }}` inside a checkout of `k8s/overlays/prod`, then `kubectl apply -k k8s/overlays/prod`. The SHA flows directly from the build-push job's own tag into the applied manifest, in-memory, in the same pipeline run — it is never written back to the repo as a commit, and no human ever hand-edits a tag.

Committed manifests in `k8s/overlays/prod/kustomization.yaml` therefore never contain a real tag — only a placeholder (or the `images:` field entirely absent, populated solely by the CI step above), so the repository's committed state never claims a specific deployed version that could drift from reality.

**"What is production running?"** resolves to one command:

```
kubectl get deployment backend -n civicpulse -o jsonpath='{.spec.template.spec.containers[0].image}'
```

which prints `ghcr.io/<org>/backend:<sha>` — that `<sha>` pastes directly into `git show <sha>`.

## Consequences

- The CD pipeline, not a human, is the only writer of a real image tag into any manifest state — committed YAML and cluster-applied YAML are allowed to differ (the cluster has a real tag, the repo has a placeholder), and that's the intended split, not drift.
- Rollback has two mechanisms, both named in §3.4: `kubectl rollout undo deployment/backend -n civicpulse` (fast, imperative — "the 3 a.m. answer," uses Kubernetes' own revision history) and re-running the `deploy-k8s` step's `kustomize edit set image` with the *previous* commit's SHA, then re-applying (slower, declarative, auditable — "the correct answer once the fire is out," because it leaves an explicit record of which SHA was redeployed and why, rather than relying on cluster-internal revision history that isn't itself versioned in git).
- Anyone auditing the repo's git history alone cannot tell what's currently deployed — that information only exists in the live cluster and in the CI run logs. This is the correct trade-off (the repo describes *desired* structure, not *current* deployed state), but it's why the CI run link and `kubectl get hpa`/deployment output are required submission evidence (§5.8) rather than something inferable from the repo alone.

## Alternatives considered

- **Deploying `:latest` directly:** rejected outright — explicit −8 automatic deduction, and it makes "what's running" unanswerable (the tag doesn't change when the image does).
- **A human manually editing a tag into the committed overlay before merging:** rejected — reintroduces a manual step between "tests passed" and "this is what's deployed," and risks the exact drift (repo says one SHA, cluster runs another) that gating by `needs:` and CI-only tag injection is meant to prevent.
- **Deploy by image digest (`@sha256:...`) instead of tag:** this is the assignment's own bonus item (§4, Bonus, "+3," requires Cosign signing/verification too) and is strictly more robust — a digest can't be reassigned to a different image the way a SHA tag theoretically could be (e.g. a re-run of `docker build` for a fully reproducible build is deterministic, but a manual `docker tag` overwrite isn't prevented by GHCR). Treated here as a documented upgrade path once the SHA-tag baseline works, not the Phase-1 baseline itself — pursuing it is one of the still-open bonus-scope questions in `docs/OPEN-DECISIONS.md` #10.
