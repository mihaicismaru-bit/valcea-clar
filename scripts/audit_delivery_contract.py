#!/usr/bin/env python3
"""F0 advisory-only delivery audit. NO network, deployment, receipts or writes.

This audit runs independently of CIVORA synchronization. It must never be
interpreted as a substitute for integration CI or actual public HTTP readback.
The five historical S5 paths are comparison candidates, NOT authorization to
ship; only an external owner-ratified manifest can supply authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
HISTORICAL_S5 = (
    "/unde-iesim/verificat/",
    "/dosare/",
    "/clarificam/restrictii-calimanesti-22-septembrie/",
    "/clarificam/somaj-valcea-august-2026/",
    "/dosare/open-air-blues-brezoi-2026/",
)
ROUTE_PATTERN = re.compile(r"^/(?:[a-z0-9-]+/)+$")
DEPLOY_ACTION = re.compile(r"^\\s*(?:-\\s*)?uses:\\s*actions/deploy-pages@v4\\s*(?:#.*)?$")
STEP_LINE = re.compile(r"^\\s{6}-\\s+")


def workflow_probe(source: str) -> dict:
    """Conservatively count *following* job steps; don't claim receipt from names."""
    lines = source.splitlines()
    deploy = [i for i, line in enumerate(lines) if DEPLOY_ACTION.fullmatch(line)]
    if len(deploy) != 1:
        return {"deploy_action_count": len(deploy), "post_deploy_steps": 0,
                "readback_certified": False, "hold": "HOLD_DEPLOY_STEP_CONTRACT"}
    # A later same-job step is required, but mere presence is NOT a receipt.
    tail = lines[deploy[0] + 1:]
    post = [line for line in tail if STEP_LINE.match(line)]
    return {"deploy_action_count": 1, "post_deploy_steps": len(post),
            "readback_certified": False,
            "hold": "HOLD_NO_POST_DEPLOY_READBACK" if not post else "HOLD_UNVERIFIED_READBACK"}


def authorize_manifest_shape(manifest: dict | None) -> tuple[str, tuple[str, ...]]:
    """Inspect shape only. 'owner_ratified' supplied by a caller is NOT verified here."""
    if not isinstance(manifest, dict) or manifest.get("approval") != "OWNER_RATIFIED":
        return "HOLD_NO_AUTHORIZED_S5_MANIFEST", ()
    if not all(isinstance(manifest.get(k), str) and manifest[k].strip()
               for k in ("approved_by", "approved_at", "source_commit")):
        return "HOLD_INCOMPLETE_S5_AUTHORITY", ()
    routes = manifest.get("required_routes")
    if not isinstance(routes, list) or len(routes) != len(set(r for r in routes if isinstance(r, str))):
        return "HOLD_INVALID_S5_ROUTES", ()
    if len(routes) != 5 or not all(isinstance(r, str) and ROUTE_PATTERN.fullmatch(r)
                                   for r in routes):
        return "HOLD_INVALID_S5_ROUTES", ()
    if set(routes) != set(HISTORICAL_S5):
        return "HOLD_S5_AUTHORITY_DIVERGENCE_REQUIRES_REVIEW", tuple(routes)
    return "S5_MANIFEST_SHAPE_OK_NOT_VERIFIED", tuple(routes)


def audit(repo: Path, manifest: dict | None = None) -> dict:
    workflow_path = repo / ".github" / "workflows" / "deploy-pages.yml"
    reasons = []
    if workflow_path.is_file():
        deploy = workflow_probe(workflow_path.read_text(encoding="utf-8"))
    else:
        deploy = {"hold": "HOLD_MISSING_DEPLOY_WORKFLOW", "post_deploy_steps": 0,
                  "readback_certified": False, "deploy_action_count": 0}
    reasons.append(deploy["hold"])
    manifest_gate, routes = authorize_manifest_shape(manifest)
    if manifest_gate != "S5_MANIFEST_SHAPE_OK_NOT_VERIFIED":
        reasons.append(manifest_gate)
    else:
        missing = [r for r in routes if not (repo / "_site" / r.strip("/") / "index.html").is_file()]
        if missing:
            reasons.append("HOLD_S5_BUILD_ARTIFACTS_MISSING")
        else:
            reasons.append("HOLD_S5_HTTP_READBACK_NOT_PERFORMED")
    return {"phase": "F0", "status": "HOLD", "delivery_certified": False,
            "can_publish": False, "can_deploy": False, "network_calls": 0,
            "workflow": deploy, "manifest_shape": manifest_gate,
            "historical_s5_comparison_only": list(HISTORICAL_S5),
            "reasons": reasons,
            "warning": "Advisory structural HOLD, not a release gate or public HTTP receipt."}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, default=REPO)
    ap.add_argument("--manifest", type=Path, help="Externally ratified JSON, inspected but not authenticated")
    args = ap.parse_args()
    if args.manifest:
        try:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(json.dumps({"status": "HOLD", "reasons": ["HOLD_MANIFEST_UNREADABLE"],
                              "detail": type(exc).__name__, "delivery_certified": False}))
            return 2
    else:
        manifest = None
    print(json.dumps(audit(args.repo_root, manifest), indent=2, ensure_ascii=False))
    return 2  # fail closed; a command success must not be interpreted as delivery


if __name__ == "__main__":
    raise SystemExit(main())
