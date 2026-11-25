"""Strict V2 protocol adapter for the frozen XAUUSD validation amendment."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

V2_IDS = tuple(f"v2_validation_{i:02d}" for i in range(1, 5))
UNVERIFIED_LOCK = "UNVERIFIED_REQUIRED_INPUT"


class V2ProtocolError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: Any, field: str, *, require_utc: bool = True) -> datetime:
    if not isinstance(value, str):
        raise V2ProtocolError(f"{field} must be an ISO-8601 timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise V2ProtocolError(f"{field} must be an ISO-8601 timezone-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V2ProtocolError(f"{field} must include a timezone offset")
    if require_utc and parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise V2ProtocolError(f"{field} must use the UTC offset")
    return parsed.astimezone(timezone.utc)


def _git_commit_time(commit_sha: str, repo_root: Path) -> datetime:
    result = subprocess.run(
        ["git", "show", "-s", "--format=%cI", commit_sha],
        cwd=repo_root, capture_output=True, text=True, check=False,
    )
    if result.returncode or not result.stdout.strip():
        raise V2ProtocolError("cannot verify the frozen implementation commit timestamp")
    return parse_utc(result.stdout.strip(), "implementation commit timestamp", require_utc=False)


def _git_path_commit(path: Path, repo_root: Path) -> tuple[datetime, str]:
    try:
        relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise V2ProtocolError("freeze and amendment files must be inside the checked-out repository") from exc
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cI%x00%H", "--", str(relative)],
        cwd=repo_root, capture_output=True, text=True, check=False,
    )
    if result.returncode or not result.stdout.strip() or "\x00" not in result.stdout:
        raise V2ProtocolError(f"{path.name} must be committed before collection")
    timestamp, commit_sha = result.stdout.strip().split("\x00", 1)
    return parse_utc(timestamp, f"{path.name} commit timestamp", require_utc=False), commit_sha


def validate_amendment_contract(amendment: dict[str, Any]) -> None:
    requirements = amendment.get("collection_requirements", {})
    expected_requirements = {
        "minimum_session_duration_seconds": 1800,
        "minimum_validation_sessions": 4,
        "minimum_validation_distinct_dates": 4,
        "minimum_outcomes_per_configuration_horizon": 100,
        "collection_mode": "PROSPECTIVE_EXNESS_DEMO_READ_ONLY",
        "canonical_symbol_only": "XAUUSD",
        "trading_enabled": False,
        "order_submission": False,
        "position_management": False,
        "dll_imports_enabled": False,
        "no_cron_or_unattended_collection": True,
        "first_and_last_partial_feature_windows_excluded": True,
        "all_required_lookback_and_compression_windows_must_be_complete": True,
        "no_cross_session_feature_history": True,
    }
    if any(requirements.get(key) != value for key, value in expected_requirements.items()):
        raise V2ProtocolError("V2 collection requirements differ from the reviewed four-session read-only contract")
    lane = amendment.get("position_lane_semantics", {})
    if (
        lane.get("lane_key") != ["candidate_id", "complete_parameter_set", "horizon_seconds"]
        or lane.get("one_open_position_per_lane") is not True
        or lane.get("horizon_arms_are_independent_counterfactual_research_streams") is not True
        or lane.get("horizons_must_not_share_or_block_each_others_research_lane") is not True
    ):
        raise V2ProtocolError("V2 candidate/horizon lane semantics differ from the reviewed replay implementation")
    evaluation = amendment.get("evaluation", {})
    if (
        evaluation.get("holding_horizons_seconds") != [5, 15, 30, 60]
        or evaluation.get("slippage_sensitivity_points_per_side") != [0, 1, 2, 5]
        or evaluation.get("commission_status") != UNVERIFIED_LOCK
        or evaluation.get("net_performance_allowed") is not False
        or evaluation.get("holdout_access") != "SEALED"
    ):
        raise V2ProtocolError("V2 evaluation cost, horizon, commission, or holdout gates changed")
    gates = amendment.get("gates", {})
    if (
        gates.get("candidate_approval") != "NOT_APPROVED"
        or gates.get("order_execution") != "DISABLED"
        or gates.get("live_trading") != "DISABLED"
        or not str(gates.get("holdout", "")).startswith("SEALED")
    ):
        raise V2ProtocolError("V2 candidate, execution, or holdout gate changed")


def load_frozen_v2(*, amendment_path: Path, freeze_path: Path, base_plan_path: Path,
                   registry_path: Path, repo_root: Path, verify_git_ancestry: bool = True):
    try:
        amendment_bytes = amendment_path.read_bytes()
        amendment = json.loads(amendment_bytes)
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        base_plan = json.loads(base_plan_path.read_text(encoding="utf-8"))
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V2ProtocolError("V2 amendment, freeze, base plan, or registry is unreadable") from exc
    if amendment.get("plan_schema") != "VELTRIX_XAUUSD_WALK_FORWARD_PLAN_V2_AMENDMENT":
        raise V2ProtocolError("unsupported V2 amendment schema")
    if amendment.get("status") != "FROZEN_PREREGISTRATION_RESEARCH_ONLY":
        raise V2ProtocolError("V2 amendment is not frozen; collection and evaluation remain blocked")
    validate_amendment_contract(amendment)
    if base_plan.get("plan_schema") != "VELTRIX_XAUUSD_WALK_FORWARD_PLAN_V1":
        raise V2ProtocolError("the immutable V1 base plan is missing or unsupported")
    registry_hash = sha256_file(registry_path)
    if amendment.get("source_registry_sha256") != registry_hash:
        raise V2ProtocolError("V2 amendment registry hash does not match the frozen registry file")
    if freeze.get("plan_sha256") != hashlib.sha256(amendment_bytes).hexdigest():
        raise V2ProtocolError("freeze record does not bind the exact V2 amendment bytes")
    if freeze.get("registry_sha256") != registry_hash:
        raise V2ProtocolError("freeze record does not bind the exact frozen registry")
    commission_lock = freeze.get("commission_evidence_sha256_or_explicit_unverified_lock")
    if commission_lock != UNVERIFIED_LOCK:
        raise V2ProtocolError("commission evidence ingestion is not implemented; retain the explicit unverified lock")
    frozen_at = parse_utc(freeze.get("frozen_utc"), "freeze.frozen_utc")
    implementation_sha = freeze.get("implementation_commit_sha")
    if not isinstance(implementation_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", implementation_sha):
        raise V2ProtocolError("freeze implementation_commit_sha must be a full commit SHA")
    if verify_git_ancestry:
        check = subprocess.run(["git", "merge-base", "--is-ancestor", implementation_sha, "HEAD"],
                               cwd=repo_root, capture_output=True, text=True, check=False)
        if check.returncode != 0:
            raise V2ProtocolError("frozen implementation commit is not an ancestor of the evaluated checkout")
    if freeze.get("collection_session_ids") != list(V2_IDS):
        raise V2ProtocolError("freeze must bind exactly the four ordered V2 session IDs")
    if amendment.get("new_validation_sessions") != [
        {"session_id": sid, "distinct_date_required": True} for sid in V2_IDS
    ]:
        raise V2ProtocolError("amendment must define exactly the four V2 session IDs")
    schedule = freeze.get("collection_schedule_utc")
    if not isinstance(schedule, list) or len(schedule) != 4:
        raise V2ProtocolError("freeze must contain four explicit UTC collection schedule entries")
    seen_dates, schedule_by_id = set(), {}
    for item in schedule:
        if not isinstance(item, dict) or item.get("session_id") not in V2_IDS:
            raise V2ProtocolError("schedule contains an unknown V2 session ID")
        sid = item["session_id"]
        if sid in schedule_by_id:
            raise V2ProtocolError("schedule contains a duplicate V2 session ID")
        start = parse_utc(item.get("start_utc"), f"{sid}.start_utc")
        end = parse_utc(item.get("end_utc"), f"{sid}.end_utc")
        if (end - start).total_seconds() < 1800 or start.date() != end.date():
            raise V2ProtocolError(f"{sid}: scheduled interval must be at least 30 minutes on one UTC date")
        if start <= frozen_at:
            raise V2ProtocolError("freeze timestamp must precede every scheduled collection")
        if start.date().isoformat() in seen_dates:
            raise V2ProtocolError("V2 collection schedule must use four distinct UTC dates")
        seen_dates.add(start.date().isoformat())
        schedule_by_id[sid] = {"start": start, "end": end}
    if set(schedule_by_id) != set(V2_IDS):
        raise V2ProtocolError("schedule must contain each V2 session exactly once")
    freeze_commit_sha = None
    if verify_git_ancestry:
        implementation_time = _git_commit_time(implementation_sha, repo_root)
        freeze_commit_time, freeze_commit_sha = _git_path_commit(freeze_path, repo_root)
        amendment_commit_time, _ = _git_path_commit(amendment_path, repo_root)
        earliest_collection = min(item["start"] for item in schedule_by_id.values())
        if implementation_time > frozen_at:
            raise V2ProtocolError("freeze timestamp predates the validated implementation commit")
        if amendment_commit_time > frozen_at:
            raise V2ProtocolError("freeze timestamp predates the committed frozen amendment")
        if amendment_commit_time > freeze_commit_time:
            raise V2ProtocolError("freeze record commit must follow the frozen amendment commit")
        if frozen_at > freeze_commit_time:
            raise V2ProtocolError("freeze timestamp is later than the committed freeze record")
        if freeze_commit_time >= earliest_collection:
            raise V2ProtocolError("freeze record commit must precede every scheduled collection")
    required = amendment.get("freeze_contract", {}).get("required_fields", [])
    if not all(field in freeze for field in required):
        raise V2ProtocolError("freeze record is missing one or more preregistered required fields")
    plan = copy.deepcopy(base_plan)
    plan["validation_sessions"] = list(V2_IDS)
    plan["collection_requirements"]["minimum_validation_sessions"] = 4
    plan["collection_requirements"]["minimum_validation_distinct_dates"] = 4
    plan["collection_requirements"]["minimum_validation_outcomes_per_configuration_horizon"] = 100
    plan["evaluation"]["commission_status"] = UNVERIFIED_LOCK
    plan["evaluation"]["net_performance_allowed"] = False
    plan["execution_enabled"] = False
    plan["live_trading_enabled"] = False
    plan["v2_protocol"] = {
        "amendment_sha256": hashlib.sha256(amendment_bytes).hexdigest(),
        "implementation_commit_sha": implementation_sha,
        "freeze_commit_sha": freeze_commit_sha,
        "freeze_utc": frozen_at.isoformat(),
        "schedule": schedule_by_id,
        "holdout_access": "SEALED",
        "candidate_approval": "NOT_APPROVED",
    }
    return plan, amendment, freeze
