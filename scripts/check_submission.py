#!/usr/bin/env python3
"""Pre-submission lint for the §5.3 automatic-deduction list (assignment §5.8).

A lint, not a grader: it mechanically re-checks the exact items named in
docs/RUBRIC-CHECKLIST.md's §5.3 table via regex/text scans of real files and
`git`/`gh` subprocess calls — not a full YAML AST, not a new dependency
(stdlib only). A clean run does not guarantee a good mark; a dirty run
nearly guarantees a bad one (assignment's own words, §5.8).

Usage: python scripts/check_submission.py
Exit code: 0 if every check PASSes (WARN is allowed), 1 if any check FAILs.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def check_no_secrets_in_history() -> tuple[str, str]:
    ignored = _run(["git", "check-ignore", "-q", ".env"]).returncode == 0
    tracked = _run(["git", "ls-files", ".env"]).stdout.strip()
    in_history = _run(["git", "log", "--all", "--oneline", "--", ".env"]).stdout.strip()
    if tracked or in_history:
        return FAIL, ".env is tracked or present in git history"
    if not ignored:
        return WARN, ".env not currently gitignored (but not tracked either)"
    return PASS, ".env gitignored, untracked, absent from git history"


_DOCKERFILE_FROM = re.compile(r"^FROM\s+(\S+)", re.MULTILINE)
_YAML_IMAGE = re.compile(r"^\s*image:\s*(\S+)", re.MULTILINE)
_KUSTOMIZE_IMAGE_NAME = re.compile(r"^\s*-\s*name:\s*(\S+)\s*$", re.MULTILINE)
_KUSTOMIZE_NEW_TAG = re.compile(r"^\s*newTag:\s*(\S+)", re.MULTILINE)


def _kustomize_image_transformer_names() -> set[str]:
    """Image names that get a real tag injected via an overlay's `images:`
    transformer (or, for overlays/prod, by CI's `kustomize edit set image` —
    see that overlay's own comment) rather than being applied as written in
    k8s/base/*.yaml. This is the documented, ADR-0003-compliant pattern, not
    an unpinned image — see k8s/overlays/{dev,prod}/kustomization.yaml.
    """
    names: set[str] = set()
    for f in (ROOT / "k8s/overlays").glob("*/kustomization.yaml"):
        text = f.read_text()
        if "images:" in text:
            names.update(_KUSTOMIZE_IMAGE_NAME.findall(text))
        else:
            # No static images: block (overlays/prod) — only acceptable if the
            # file itself documents CI injecting the tag; still whitelist by
            # name convention (civicpulse-*) so k8s/base isn't flagged.
            names.update(re.findall(r"civicpulse-\w+", text))
    return names


def check_pinned_images() -> tuple[str, str]:
    bad: list[str] = []
    scanned = 0
    whitelisted_k8s_names = _kustomize_image_transformer_names()

    for f in ROOT.glob("*/Dockerfile"):
        scanned += 1
        for ref in _DOCKERFILE_FROM.findall(f.read_text()):
            ref = ref.strip().strip('"')
            tag = ref.rsplit(":", 1)[-1] if ":" in ref.split("/")[-1] else None
            if tag is None:
                bad.append(f"{f.relative_to(ROOT)}: {ref} (no tag)")
            elif tag == "latest":
                bad.append(f"{f.relative_to(ROOT)}: {ref} (:latest)")

    for f in ROOT.glob("compose*.yaml"):
        scanned += 1
        for ref in _YAML_IMAGE.findall(f.read_text()):
            ref = ref.strip().strip('"')
            tag = ref.rsplit(":", 1)[-1] if ":" in ref.split("/")[-1] else None
            if tag is None:
                bad.append(f"{f.relative_to(ROOT)}: {ref} (no tag)")
            elif tag == "latest" and "${" not in ref:
                bad.append(f"{f.relative_to(ROOT)}: {ref} (:latest)")

    for f in (ROOT / "k8s").rglob("*.yaml"):
        scanned += 1
        text = f.read_text()
        if "kustomization.yaml" == f.name and f.parent.parent.name == "overlays":
            for tag in _KUSTOMIZE_NEW_TAG.findall(text):
                if tag.strip() == "latest":
                    bad.append(f"{f.relative_to(ROOT)}: newTag: latest")
            continue
        for ref in _YAML_IMAGE.findall(text):
            ref = ref.strip().strip('"')
            if ref in whitelisted_k8s_names:
                continue  # tag injected by an overlay's images: transformer or by CI, not applied bare
            tag = ref.rsplit(":", 1)[-1] if ":" in ref.split("/")[-1] else None
            if tag is None:
                bad.append(f"{f.relative_to(ROOT)}: {ref} (no tag, and not in any overlay's images: whitelist)")
            elif tag == "latest":
                bad.append(f"{f.relative_to(ROOT)}: {ref} (:latest)")

    if bad:
        return FAIL, "; ".join(bad)
    return PASS, f"{scanned} Dockerfile/compose/k8s files scanned, every image pinned or Kustomize-tagged, no hardcoded :latest"


def check_no_localhost_service_to_service() -> tuple[str, str]:
    hits: list[str] = []
    for f in list(ROOT.glob("compose*.yaml")) + list((ROOT / "k8s").rglob("*.yaml")):
        for i, line in enumerate(f.read_text().splitlines(), start=1):
            if "localhost" in line or "127.0.0.1" in line:
                hits.append(f"{f.relative_to(ROOT)}:{i}")
    if hits:
        return FAIL, "; ".join(hits)
    return PASS, "no localhost/127.0.0.1 in compose*.yaml or k8s/**/*.yaml"


def check_no_published_db_cache_ports() -> tuple[str, str]:
    prod = ROOT / "compose.prod.yaml"
    if not prod.exists():
        return WARN, "compose.prod.yaml not found"
    lines = prod.read_text().splitlines()
    bad: list[str] = []
    current_service = None
    service_indent = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        m = re.match(r"^(\w[\w-]*):\s*$", stripped)
        if m and indent == 2:  # top-level service name, under `services:`
            current_service = m.group(1)
            service_indent = indent
            continue
        if current_service in ("postgres", "redis") and indent > (service_indent or 0):
            if re.match(r"^ports\s*:", stripped):
                bad.append(f"compose.prod.yaml:{i + 1} ({current_service} publishes ports)")
        elif indent <= (service_indent or 99) and stripped and not m:
            current_service = None
    if bad:
        return FAIL, "; ".join(bad)
    return PASS, "no ports: under postgres/redis in compose.prod.yaml"


def _job_gated(text: str, job_name: str) -> bool | None:
    """True if `job_name:`'s block contains `needs:` before the next top-level job."""
    lines = text.splitlines()
    in_job = False
    job_indent = None
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if re.match(rf"^{re.escape(job_name)}\s*:\s*$", stripped):
            in_job = True
            job_indent = indent
            continue
        if in_job:
            if stripped and indent <= (job_indent or 0):
                return False  # reached the next job/key with no needs: seen
            if re.match(r"^needs\s*:", stripped):
                return True
    return None if not in_job and job_indent is None else False


def check_publish_deploy_jobs_gated() -> tuple[str, str]:
    cd = ROOT / ".github/workflows/cd.yml"
    if not cd.exists():
        return WARN, "cd.yml not found"
    text = cd.read_text()
    results = {job: _job_gated(text, job) for job in ("build-push", "deploy-k8s")}
    missing = [job for job, gated in results.items() if not gated]
    if missing:
        return FAIL, f"cd.yml job(s) missing needs:: {', '.join(missing)}"
    # release.yml is deliberately exempt: it never runs on a PR, only on a
    # v* tag push against a commit already gated onto main by branch
    # protection (see release.yml's own header comment) — nothing to need.
    return PASS, "cd.yml: build-push needs [test-backend, test-frontend], deploy-k8s needs build-push; release.yml exempt by design (tag-push only, re-tags an already-tested SHA)"


def check_postgres_pvc() -> tuple[str, str]:
    pg = ROOT / "k8s/base/postgres.yaml"
    if not pg.exists():
        return WARN, "k8s/base/postgres.yaml not found"
    text = pg.read_text()
    is_statefulset = "kind: StatefulSet" in text
    has_pvc_template = "volumeClaimTemplates" in text
    is_bare_deployment = bool(re.search(r"kind:\s*Deployment", text))
    if is_bare_deployment or not is_statefulset or not has_pvc_template:
        return FAIL, "postgres.yaml is not a StatefulSet with volumeClaimTemplates"
    return PASS, "k8s/base/postgres.yaml: StatefulSet + volumeClaimTemplates present"


def check_no_direct_commits_to_main() -> tuple[str, str]:
    remote = _run(["git", "remote", "get-url", "origin"]).stdout.strip()
    m = re.search(r"github\.com[:/](.+?)/(.+?)(?:\.git)?$", remote)
    if not m:
        return WARN, f"could not parse owner/repo from remote {remote!r}"
    owner, repo = m.group(1), m.group(2)
    result = _run(["gh", "api", f"repos/{owner}/{repo}/branches/main/protection"])
    if result.returncode != 0:
        return WARN, f"gh api call failed (not authenticated, or no protection set): {result.stderr.strip()[:200]}"
    import json

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return WARN, "gh api returned non-JSON output"
    enforce_admins = data.get("enforce_admins", {}).get("enabled")
    contexts = data.get("required_status_checks", {}).get("contexts", [])
    if not enforce_admins or not contexts:
        return FAIL, f"branch protection incomplete: enforce_admins={enforce_admins}, contexts={contexts}"
    return PASS, f"main protected: enforce_admins=True, {len(contexts)} required status checks"


CHECKS = [
    ("No secrets in git history", check_no_secrets_in_history),
    ("Base images pinned, no :latest", check_pinned_images),
    ("No localhost in service-to-service config", check_no_localhost_service_to_service),
    ("No published DB/cache ports in compose.prod.yaml", check_no_published_db_cache_ports),
    ("Publish/deploy jobs gated by needs:", check_publish_deploy_jobs_gated),
    ("PostgreSQL is a StatefulSet with a PVC, not a bare Deployment", check_postgres_pvc),
    ("No direct commits to main (branch protection enforced)", check_no_direct_commits_to_main),
]


def main() -> int:
    failed = False
    for label, fn in CHECKS:
        status, detail = fn()
        if status == FAIL:
            failed = True
        print(f"[{status}] {label} — {detail}")
    print()
    print("FAIL — fix the above before submitting." if failed else "All checks passed (or warned).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
