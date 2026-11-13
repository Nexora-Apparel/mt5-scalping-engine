"""Download completed XAUUSD DEMO collection artifacts and build a walk-forward catalog.

This helper uses the GitHub CLI and the caller's read-only GITHUB_TOKEN. It never
connects to MT5, accesses broker credentials, or enables trading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ArtifactIntakeError(ValueError):
    pass


def _gh_json(args: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["gh", "api", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ArtifactIntakeError(f"GitHub CLI request failed for endpoint {args[0]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ArtifactIntakeError("GitHub CLI returned invalid JSON") from exc


def validate_session_map(
    mapping: dict[str, Any],
    plan: dict[str, Any],
    *,
    stage: str,
) -> list[dict[str, Any]]:
    if stage != "validation":
        raise ArtifactIntakeError("final holdout artifact intake is sealed until commission verification")
    sessions = mapping.get("sessions") if isinstance(mapping, dict) else None
    if not isinstance(sessions, list):
        raise ArtifactIntakeError("session map must contain a sessions array")
    development = {item["session_id"]: item for item in plan["development_sessions"]}
    validation = set(plan["validation_sessions"])
    ineligible = {entry["session_id"] for entry in plan.get("ineligible_validation_sessions", [])}
    allowed = set(development) | validation
    seen: set[str] = set()
    normalized = []
    for item in sessions:
        if not isinstance(item, dict):
            raise ArtifactIntakeError("each session map item must be an object")
        sid, run_id = item.get("session_id"), item.get("run_id")
        if sid in ineligible:
            raise ArtifactIntakeError(f"{sid}: session is explicitly ineligible for distinct-date validation")
        if sid not in allowed:
            raise ArtifactIntakeError(f"session ID is not allowed in validation intake: {sid}")
        if sid in seen:
            raise ArtifactIntakeError(f"duplicate session ID: {sid}")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
            raise ArtifactIntakeError(f"{sid}: run_id must be a positive integer")
        if sid in development and run_id != development[sid].get("workflow_run_id"):
            raise ArtifactIntakeError(f"{sid}: run_id differs from the preregistered development workflow run")
        seen.add(sid)
        normalized.append({"session_id": sid, "run_id": run_id})
    selected_validation = {item["session_id"] for item in normalized} & validation
    if selected_validation != validation:
        missing = sorted(validation - selected_validation)
        raise ArtifactIntakeError(f"validation intake requires all preregistered eligible sessions together; missing={missing}")
    return normalized


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_session_artifacts(
    session_map: list[dict[str, Any]],
    plan: dict[str, Any],
    *,
    repo: str,
    workspace: Path,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ArtifactIntakeError("repository must be owner/name")
    research_dir = workspace / "research"
    session_root = research_dir / "xauusd_sessions"
    session_root.mkdir(parents=True, exist_ok=True)
    development = {item["session_id"]: item["expected_sha256"] for item in plan["development_sessions"]}
    catalog_items = []
    validation_dates: dict[str, str] = {}
    ineligible_dates = {entry["collection_date_utc"] for entry in plan.get("ineligible_validation_sessions", [])}

    for item in session_map:
        sid, run_id = item["session_id"], item["run_id"]
        run = _gh_json([f"repos/{repo}/actions/runs/{run_id}"], cwd=workspace)
        if run.get("conclusion") != "success" or run.get("status") != "completed":
            raise ArtifactIntakeError(f"{sid}: collection workflow run is not completed successfully")
        artifacts = _gh_json([f"repos/{repo}/actions/runs/{run_id}/artifacts"], cwd=workspace).get("artifacts", [])
        matches = [
            artifact for artifact in artifacts
            if artifact.get("name", "").startswith("veltrix-exness-demo-ticks-")
            and artifact.get("expired") is False
        ]
        if len(matches) != 1:
            raise ArtifactIntakeError(f"{sid}: expected exactly one unexpired XAUUSD tick artifact")
        artifact_name = matches[0]["name"]
        expected_artifact_id = next(
            (entry.get("artifact_id") for entry in plan["development_sessions"] if entry["session_id"] == sid),
            None,
        )
        if expected_artifact_id is not None and matches[0].get("id") != expected_artifact_id:
            raise ArtifactIntakeError(f"{sid}: artifact ID differs from the preregistered development artifact")
        destination = session_root / sid
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        download = subprocess.run(
            ["gh", "run", "download", str(run_id), "--repo", repo, "--name", artifact_name, "--dir", str(destination)],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        if download.returncode:
            raise ArtifactIntakeError(f"{sid}: artifact download failed")
        csv_files = list(destination.rglob("veltrix_exness_demo_ticks.csv"))
        manifests = list(destination.rglob("manifest.json"))
        if len(csv_files) != 1 or len(manifests) != 1:
            raise ArtifactIntakeError(f"{sid}: artifact must contain exactly one CSV and one manifest")
        csv_path, manifest_path = csv_files[0], manifests[0]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = _sha256(csv_path)
        development_entry = next((entry for entry in plan["development_sessions"] if entry["session_id"] == sid), None)
        if development_entry is not None:
            if _sha256(manifest_path) != development_entry.get("expected_manifest_sha256"):
                raise ArtifactIntakeError(f"{sid}: development manifest hash differs from the preregistered manifest")
            for field in ("collection_started_utc", "collection_ended_utc", "duration_seconds"):
                if manifest.get(field) != development_entry.get(field):
                    raise ArtifactIntakeError(f"{sid}: development manifest {field} differs from the preregistered value")
        if manifest.get("sha256") != digest:
            raise ArtifactIntakeError(f"{sid}: CSV hash does not match the artifact manifest")
        if manifest.get("status") != "PASS" or manifest.get("data_audit_status") != "PASS":
            raise ArtifactIntakeError(f"{sid}: collection or data-audit status is not PASS")
        if manifest.get("duration_clock") != "monotonic" or float(manifest.get("duration_seconds", 0)) < plan["collection_requirements"]["minimum_session_duration_seconds"]:
            raise ArtifactIntakeError(f"{sid}: session is shorter than the preregistered minimum or lacks monotonic duration")
        if manifest.get("account_mode") != "DEMO" or manifest.get("trading_enabled") is not False or manifest.get("dll_imports_enabled") is not False:
            raise ArtifactIntakeError(f"{sid}: manifest is not read-only DEMO")
        if set(manifest.get("symbols", {})) != {"XAUUSD"} or set(manifest.get("instrument_specs", {})) != {"XAUUSD"}:
            raise ArtifactIntakeError(f"{sid}: artifact is not XAUUSD-only")
        spec = manifest["instrument_specs"]["XAUUSD"]
        if spec.get("currency_base") != "XAU" or spec.get("currency_profit") != "USD":
            raise ArtifactIntakeError(f"{sid}: broker contract metadata is not XAUUSD")
        if sid in development and digest != development[sid]:
            raise ArtifactIntakeError(f"{sid}: development artifact hash differs from preregistered hash")
        if sid not in development and manifest.get("session_id") != sid:
            raise ArtifactIntakeError(f"{sid}: manifest session_id does not match the preregistered validation ID")
        if sid not in development:
            try:
                started = datetime.fromisoformat(str(manifest["collection_started_utc"]).replace("Z", "+00:00"))
                if started.tzinfo is None:
                    raise ValueError("timestamp has no timezone")
                collection_date = started.astimezone(timezone.utc).date().isoformat()
            except (KeyError, TypeError, ValueError) as exc:
                raise ArtifactIntakeError(f"{sid}: invalid UTC collection start timestamp") from exc
            if collection_date in ineligible_dates:
                raise ArtifactIntakeError(f"{sid}: collection date {collection_date} is already disqualified")
            if collection_date in validation_dates:
                other = validation_dates[collection_date]
                raise ArtifactIntakeError(f"{sid}: shares UTC collection date {collection_date} with {other}; distinct dates required")
            validation_dates[collection_date] = sid
        if sid not in development and digest in set(development.values()):
            raise ArtifactIntakeError(f"{sid}: inspected development artifact cannot be promoted to validation")

        # Flatten only the two verified data files into a stable session directory.
        final_dir = session_root / sid
        final_csv = final_dir / "veltrix_exness_demo_ticks.csv"
        final_manifest = final_dir / "manifest.json"
        if csv_path != final_csv:
            shutil.copy2(csv_path, final_csv)
        if manifest_path != final_manifest:
            shutil.copy2(manifest_path, final_manifest)
        for child in list(final_dir.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
            elif child.name not in {final_csv.name, final_manifest.name}:
                child.unlink()
        catalog_items.append({
            "session_id": sid,
            "csv": f"xauusd_sessions/{sid}/veltrix_exness_demo_ticks.csv",
            "manifest": f"xauusd_sessions/{sid}/manifest.json",
        })

    catalog = {
        "catalog_schema": "VELTRIX_XAUUSD_WALK_FORWARD_CATALOG_V1",
        "sessions": catalog_items,
    }
    catalog_path = research_dir / "xauusd_walk_forward_catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return {"catalog_path": catalog_path, "sessions_downloaded": len(catalog_items), "catalog": catalog}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-map", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=Path("research/xauusd_walk_forward_plan_v1.json"))
    parser.add_argument("--stage", choices=("validation", "holdout"), default="validation")
    parser.add_argument("--repo", default="")
    args = parser.parse_args()
    workspace = Path.cwd()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        mapping = json.loads(args.session_map.read_text(encoding="utf-8"))
        normalized = validate_session_map(mapping, plan, stage=args.stage)
        result = download_session_artifacts(normalized, plan, repo=args.repo, workspace=workspace)
    except (OSError, json.JSONDecodeError, ArtifactIntakeError, KeyError, TypeError) as exc:
        parser.exit(2, f"ARTIFACT INTAKE BLOCKED: {exc}\n")
    print(json.dumps({
        "status": "ARTIFACTS_DOWNLOADED",
        "sessions_downloaded": result["sessions_downloaded"],
        "catalog_path": str(result["catalog_path"]),
        "trading_enabled": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
