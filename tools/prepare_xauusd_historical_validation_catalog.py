"""Prepare preregistered Phase 8 validation sessions from verified historical tick artifacts.

Historical quotes are assigned to validation IDs only after exact date/window,
provenance, DEMO safety, contract metadata, and hash checks. The source manifests
are preserved as derived copies; no raw CSV or source manifest is rewritten.
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

from tools.mt5_tick_market_profile import profile_dataset
from tools.prepare_xauusd_walk_forward_catalog import validate_session_map, download_session_artifacts

PINNED_SOURCE_COMMIT = "1b8b6bf518a0bc997611183f0120295b82588a5e"
EXPECTED_RUN_ID = 44654151366
EXPECTED_RUN_HEAD_SHA = "312178a9401d69322d031f26ea9296b457802337"
EXPECTED_ARTIFACT_ID = 14592042454
EXPECTED_ARTIFACT_DIGEST = "sha256:a3387bde442bc657ec9489c54c71853acdae4844bf1a25ce8fea5159f8bd2f75"
EXPECTED_VALIDATION_IDS = ("validation_01", "validation_02", "validation_03", "validation_04")
MINIMUM_START = datetime(2026, 11, 14, tzinfo=timezone.utc)


class HistoricalIntakeError(ValueError):
    pass


def _gh_json(args: list[str], cwd: Path) -> Any:
    result = subprocess.run(["gh", "api", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise HistoricalIntakeError(f"GitHub API request failed: {args[0]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HistoricalIntakeError("GitHub API returned invalid JSON") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_map(value: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = value.get("sessions") if isinstance(value, dict) else None
    if not isinstance(sessions, list) or len(sessions) != 4:
        raise HistoricalIntakeError("exactly four preregistered validation sessions are required")
    normalized = []
    seen_ids, seen_intervals, seen_dates = set(), set(), set()
    for item in sessions:
        if not isinstance(item, dict) or set(item) != {"session_id", "run_id", "interval_id"}:
            raise HistoricalIntakeError("each map item must contain session_id, run_id, and interval_id")
        sid, run_id, interval_id = item["session_id"], item["run_id"], item["interval_id"]
        if sid not in EXPECTED_VALIDATION_IDS or sid in seen_ids:
            raise HistoricalIntakeError("validation session IDs must be the four unique preregistered IDs")
        if run_id != EXPECTED_RUN_ID:
            raise HistoricalIntakeError("historical run ID differs from the audited ten-date batch")
        if not isinstance(interval_id, str) or not re.fullmatch(r"ny_202611(16|17|18|19)_1730", interval_id):
            raise HistoricalIntakeError("interval ID is outside the audited Nov 16–19 New York sample")
        date_key = interval_id[3:11]
        if date_key in seen_dates or interval_id in seen_intervals:
            raise HistoricalIntakeError("historical validation intervals must use four distinct dates")
        seen_ids.add(sid); seen_intervals.add(interval_id); seen_dates.add(date_key)
        normalized.append({"session_id": sid, "run_id": run_id, "interval_id": interval_id})
    if seen_ids != set(EXPECTED_VALIDATION_IDS):
        raise HistoricalIntakeError("all four preregistered validation IDs must be supplied")
    return normalized


def prepare(mapping: list[dict[str, Any]], *, repo: str, workspace: Path) -> dict[str, Any]:
    run = _gh_json([f"repos/{repo}/actions/runs/{EXPECTED_RUN_ID}"], workspace)
    if (
        run.get("status") != "completed" or run.get("conclusion") != "success"
        or run.get("head_sha") != EXPECTED_RUN_HEAD_SHA
    ):
        raise HistoricalIntakeError("historical backfill workflow status or dispatcher commit differs from the audited run")
    artifacts = _gh_json([f"repos/{repo}/actions/runs/{EXPECTED_RUN_ID}/artifacts"], workspace).get("artifacts", [])
    matches = [item for item in artifacts if item.get("name") == "veltrix-xauusd-historical-batch-5" and item.get("expired") is False]
    if len(matches) != 1:
        raise HistoricalIntakeError("expected exactly one unexpired audited historical batch artifact")
    if matches[0].get("id") != EXPECTED_ARTIFACT_ID or matches[0].get("digest") != EXPECTED_ARTIFACT_DIGEST:
        raise HistoricalIntakeError("historical batch artifact ID or SHA-256 differs from the independently recorded evidence")
    artifact_name = matches[0]["name"]
    download_root = workspace / "research" / "historical_validation_source"
    if download_root.exists():
        shutil.rmtree(download_root)
    download_root.mkdir(parents=True)
    downloaded = subprocess.run(
        ["gh", "run", "download", str(EXPECTED_RUN_ID), "--repo", repo, "--name", artifact_name, "--dir", str(download_root)],
        cwd=workspace, capture_output=True, text=True, check=False,
    )
    if downloaded.returncode:
        raise HistoricalIntakeError("historical batch artifact download failed")
    batch_files = list(download_root.rglob("batch_manifest.json"))
    if len(batch_files) != 1:
        raise HistoricalIntakeError("artifact must contain exactly one batch manifest")
    batch_path = batch_files[0]
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    if batch.get("status") != "PASS" or batch.get("failed_count") != 0:
        raise HistoricalIntakeError("historical batch manifest is not a complete PASS")
    if batch.get("source_commit") != PINNED_SOURCE_COMMIT:
        raise HistoricalIntakeError("historical retrieval source commit differs from reviewed pinned source")
    interval_index = {item.get("id"): item for item in batch.get("intervals", [])}
    plan = json.loads((workspace / "research" / "xauusd_walk_forward_plan_v1.json").read_text(encoding="utf-8"))
    development_map = {"sessions": [
        {"session_id": "session8", "run_id": 43333365050},
        {"session_id": "session9", "run_id": 43338046880},
    ]}
    normalized_development = validate_session_map(development_map, plan, stage="validation")
    development_result = download_session_artifacts(
        normalized_development, plan, repo=repo, workspace=workspace
    )
    catalog_items = list(development_result["catalog"]["sessions"])
    session_root = workspace / "research" / "xauusd_sessions"
    session_root.mkdir(parents=True, exist_ok=True)
    dates = set()
    for item in mapping:
        sid, interval_id = item["session_id"], item["interval_id"]
        interval = interval_index.get(interval_id)
        if not isinstance(interval, dict) or interval.get("status") != "PASS":
            raise HistoricalIntakeError(f"{interval_id}: batch manifest does not record PASS")
        start = datetime.fromisoformat(interval["from_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
        end = datetime.fromisoformat(interval["to_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
        if start < MINIMUM_START or start.strftime("%H:%M:%S") != "17:30:00" or end.strftime("%H:%M:%S") != "18:00:00":
            raise HistoricalIntakeError(f"{interval_id}: not a post-development exact 17:30–18:00 UTC interval")
        if (end - start).total_seconds() < 1800 or start.date() != end.date() or start.date().isoformat() in dates:
            raise HistoricalIntakeError(f"{interval_id}: interval duration/date is invalid or duplicated")
        dates.add(start.date().isoformat())
        source_dir = batch_path.parent / interval_id
        csv_path = source_dir / "xauusd_historical_ticks.csv"
        manifest_path = source_dir / "manifest.json"
        if not csv_path.is_file() or not manifest_path.is_file():
            raise HistoricalIntakeError(f"{interval_id}: source CSV or manifest is missing")
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = _sha256(csv_path)
        if source_manifest.get("schema") != "VELTRIX_XAUUSD_HISTORICAL_TICK_PROBE_V2":
            raise HistoricalIntakeError(f"{interval_id}: unsupported historical manifest schema")
        if (
            source_manifest.get("sha256") != digest
            or interval.get("dataset_sha256") != digest
            or interval.get("records") != source_manifest.get("records")
            or source_manifest.get("requested_start_utc") != interval.get("from_utc")
            or source_manifest.get("requested_end_utc") != interval.get("to_utc")
        ):
            raise HistoricalIntakeError(f"{interval_id}: CSV hash, record count, or exact interval bounds differ across manifests")
        if (
            source_manifest.get("status") != "PASS"
            or source_manifest.get("account_mode") != "DEMO"
            or source_manifest.get("trading_enabled") is not False
            or source_manifest.get("dll_imports_enabled") is not False
            or source_manifest.get("order_submission") is not False
            or source_manifest.get("position_management") is not False
            or source_manifest.get("canonical_symbol") != "XAUUSD"
            or source_manifest.get("source") != "authenticated Exness MT5 DEMO terminal historical tick API"
            or source_manifest.get("source_commit") != PINNED_SOURCE_COMMIT
            or source_manifest.get("source_ref") != "phase8-historical-batch-backfill"
            or source_manifest.get("dispatcher_commit") != EXPECTED_RUN_HEAD_SHA
        ):
            raise HistoricalIntakeError(f"{interval_id}: source provenance or read-only DEMO controls failed")
        spec = source_manifest.get("instrument_specs", {}).get("XAUUSD", {})
        if (
            set(source_manifest.get("instrument_specs", {})) != {"XAUUSD"}
            or spec.get("currency_base") != "XAU"
            or spec.get("currency_profit") != "USD"
            or spec.get("broker_symbol") != "XAUUSDm"
            or float(spec.get("point", 0)) != 0.001
        ):
            raise HistoricalIntakeError(f"{interval_id}: XAUUSD contract metadata is not verified")
        profile = profile_dataset(csv_path, manifest_path, allow_legacy_historical=True)
        if profile.get("status") != "PASS":
            raise HistoricalIntakeError(f"{interval_id}: historical dataset profile is not PASS")
        derived = dict(source_manifest)
        derived.update({
            "session_id": sid,
            "collection_started_utc": start.isoformat(),
            "collection_ended_utc": end.isoformat(),
            "duration_seconds": (end - start).total_seconds(),
            "duration_clock": "historical_interval",
            "historical_validation_attestation": {
                "data_role": "PREREGISTERED_VALIDATION",
                "original_interval_id": interval_id,
                "historical_batch_run_id": EXPECTED_RUN_ID,
                "historical_batch_artifact_id": matches[0]["id"],
                "original_source_manifest_sha256": _sha256(manifest_path),
                "retrieval_mode": "authenticated_exness_demo_historical_ticks",
                "not_prospective_capture": True,
                "not_actual_fills": True,
                "pre_evaluation_exposure": "Aggregate absolute midpoint displacement and quote-movement diagnostics only; no candidate signals, candidate returns, benchmark comparisons, or parameter rankings were evaluated on these dates.",
                "candidate_registry_frozen_utc": "2026-11-13T06:17:49Z",
            },
        })
        destination = session_root / sid
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        final_csv = destination / "veltrix_exness_demo_ticks.csv"
        final_manifest = destination / "manifest.json"
        shutil.copy2(csv_path, final_csv)
        final_manifest.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        catalog_items.append({
            "session_id": sid,
            "csv": f"xauusd_sessions/{sid}/veltrix_exness_demo_ticks.csv",
            "manifest": f"xauusd_sessions/{sid}/manifest.json",
        })
    catalog = {"catalog_schema": "VELTRIX_XAUUSD_WALK_FORWARD_CATALOG_V1", "sessions": catalog_items}
    catalog_path = workspace / "research" / "xauusd_walk_forward_catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return {"catalog_path": str(catalog_path), "sessions_prepared": len(catalog_items), "dates": sorted(dates)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-map", type=Path, required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    workspace = Path.cwd()
    try:
        mapping = validate_map(json.loads(args.session_map.read_text(encoding="utf-8")))
        result = prepare(mapping, repo=args.repo, workspace=workspace)
    except (OSError, json.JSONDecodeError, HistoricalIntakeError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"HISTORICAL VALIDATION INTAKE BLOCKED: {exc}\n")
    print(json.dumps({"status": "HISTORICAL_VALIDATION_CATALOG_READY", **result, "trading_enabled": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
