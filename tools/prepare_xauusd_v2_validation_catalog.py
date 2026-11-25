"""Intake exactly four fresh prospective V2 XAUUSD DEMO validation artifacts."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from tools.prepare_xauusd_walk_forward_catalog import ArtifactIntakeError, download_session_artifacts
from tools.mt5_xauusd_v2_protocol import V2_IDS, V2ProtocolError, load_frozen_v2, parse_utc


def validate_v2_map(value: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = value.get("sessions") if isinstance(value, dict) else None
    if not isinstance(sessions, list) or len(sessions) != 4:
        raise ArtifactIntakeError("V2 intake requires exactly four session/run mappings")
    seen_ids, seen_runs = set(), set()
    normalized = []
    for item in sessions:
        if not isinstance(item, dict) or set(item) != {"session_id", "run_id"}:
            raise ArtifactIntakeError("each V2 map item must contain only session_id and run_id")
        sid, run_id = item["session_id"], item["run_id"]
        if sid not in V2_IDS or sid in seen_ids:
            raise ArtifactIntakeError("only the four unique V2 session IDs are accepted; V1 IDs are prohibited")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0 or run_id in seen_runs:
            raise ArtifactIntakeError("each V2 session must reference a distinct positive workflow run ID")
        seen_ids.add(sid)
        seen_runs.add(run_id)
        normalized.append({"session_id": sid, "run_id": run_id})
    if seen_ids != set(V2_IDS):
        raise ArtifactIntakeError("all four V2 session IDs are required")
    return normalized


def validate_schedule(catalog: dict[str, Any], workspace: Path, plan: dict[str, Any], mapping: list[dict[str, Any]], repo: str) -> None:
    entries = {item["session_id"]: item for item in catalog.get("sessions", [])}
    if set(entries) != set(V2_IDS):
        raise ArtifactIntakeError("catalog must contain exactly the four V2 validation sessions")
    observed_dates = set()
    run_by_sid = {item["session_id"]: item["run_id"] for item in mapping}
    for sid in V2_IDS:
        manifest_path = workspace / "research" / entries[sid]["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_result = subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/runs/{run_by_sid[sid]}"],
            cwd=workspace, capture_output=True, text=True, check=False,
        )
        if run_result.returncode:
            raise ArtifactIntakeError(f"{sid}: cannot verify the originating GitHub Actions run")
        run = json.loads(run_result.stdout)
        if (
            run.get("status") != "completed" or run.get("conclusion") != "success"
            or run.get("event") != "workflow_dispatch"
            or run.get("path") != ".github/workflows/xauusd-v2-demo-validation-collection.yml"
            or run.get("head_branch") != "main"
        ):
            raise ArtifactIntakeError(f"{sid}: artifact did not originate from the successful manual V2 workflow on main")
        source_commit = manifest.get("source_commit_sha")
        if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
            raise ArtifactIntakeError(f"{sid}: manifest lacks a valid source commit SHA")
        if source_commit != run.get("head_sha"):
            raise ArtifactIntakeError(f"{sid}: manifest source commit does not match the originating workflow run")
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor",
             plan["v2_protocol"]["implementation_commit_sha"], source_commit],
            cwd=workspace, capture_output=True, text=True, check=False,
        )
        if ancestor.returncode:
            raise ArtifactIntakeError(f"{sid}: collection source commit does not contain the frozen implementation")
        if manifest.get("session_id") != sid or manifest.get("account_mode") != "DEMO":
            raise ArtifactIntakeError(f"{sid}: manifest identity/account mode mismatch")
        if manifest.get("trading_enabled") is not False or manifest.get("dll_imports_enabled") is not False:
            raise ArtifactIntakeError(f"{sid}: read-only DEMO controls are not attested")
        if manifest.get("order_submission") is not False or manifest.get("position_management") is not False:
            raise ArtifactIntakeError(f"{sid}: order/position controls are not explicitly disabled")
        if manifest.get("duration_clock") != "monotonic" or float(manifest.get("duration_seconds", 0)) < 1800:
            raise ArtifactIntakeError(f"{sid}: prospective monotonic collection is shorter than 30 minutes")
        start = parse_utc(manifest.get("collection_started_utc"), f"{sid}.collection_started_utc")
        end = parse_utc(manifest.get("collection_ended_utc"), f"{sid}.collection_ended_utc")
        if (end - start).total_seconds() < 1800 or start.date() != end.date():
            raise ArtifactIntakeError(f"{sid}: invalid collection interval")
        if start.date().isoformat() in observed_dates:
            raise ArtifactIntakeError("V2 sessions must come from four distinct UTC dates")
        observed_dates.add(start.date().isoformat())
        schedule = plan["v2_protocol"]["schedule"][sid]
        if abs((start - schedule["start"]).total_seconds()) > 600:
            raise ArtifactIntakeError(f"{sid}: actual collection start is outside the frozen +/-10 minute schedule window")
    if len(observed_dates) != 4:
        raise ArtifactIntakeError("V2 validation distinct-date requirement failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-map", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, default=Path("research/xauusd_walk_forward_plan_v2_amendment.json"))
    parser.add_argument("--freeze", type=Path, default=Path("research/xauusd_v2_freeze.json"))
    parser.add_argument("--base-plan", type=Path, default=Path("research/xauusd_walk_forward_plan_v1.json"))
    parser.add_argument("--registry", type=Path, default=Path("research/xauusd_strategy_registry_v1.json"))
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    workspace = Path.cwd()
    try:
        plan, _, _ = load_frozen_v2(
            amendment_path=args.amendment, freeze_path=args.freeze,
            base_plan_path=args.base_plan, registry_path=args.registry,
            repo_root=workspace,
        )
        mapping = validate_v2_map(json.loads(args.session_map.read_text(encoding="utf-8")))
        result = download_session_artifacts(mapping, plan, repo=args.repo, workspace=workspace)
        validate_schedule(result["catalog"], workspace, plan, mapping, args.repo)
    except (OSError, json.JSONDecodeError, ArtifactIntakeError, V2ProtocolError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"V2 ARTIFACT INTAKE BLOCKED: {exc}\\n")
    print(json.dumps({
        "status": "V2_ARTIFACTS_ACCEPTED",
        "sessions_downloaded": result["sessions_downloaded"],
        "catalog_path": str(result["catalog_path"]),
        "commission_status": plan["evaluation"]["commission_status"],
        "net_performance_allowed": False,
        "holdout_access": "SEALED",
        "order_submission": False,
        "position_management": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
