"""Chronological, cost-aware XAUUSD walk-forward research evaluator.

Only verified Exness DEMO XAUUSD datasets are accepted. Outputs are research-only;
this module never submits, prepares, or authorizes broker orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.mt5_tick_market_profile import ProfileError, profile_dataset
from tools.mt5_xauusd_candidate_signals import CandidateError, generate_candidate_events
from tools.mt5_xauusd_feature_research import build_features
from tools.mt5_xauusd_strategy_registry import RegistryError, validate_registry
from tools.mt5_xauusd_commission import (
    CommissionEvidenceError, net_return_bps, validate_commission_evidence,
)
from tools.mt5_xauusd_tick_replay import (
    ReplayError, evaluate_event, load_verified_ticks, replay_events,
)


class WalkForwardError(ValueError):
    """Raised when a walk-forward plan, session, or selection freeze is invalid."""


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise WalkForwardError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WalkForwardError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise WalkForwardError(f"{field} must be timezone-aware UTC")
    return parsed.astimezone(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit_utc(path: Path, cwd: Path) -> datetime:
    root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=cwd,
        capture_output=True, text=True, check=False,
    )
    if root_result.returncode or not root_result.stdout.strip():
        raise WalkForwardError("Git repository metadata is required to verify holdout freeze commits")
    root = Path(root_result.stdout.strip()).resolve()
    try:
        relative = path.resolve().relative_to(root)
    except ValueError as exc:
        raise WalkForwardError("selection-freeze and validation-report files must be inside the repository") from exc
    commit_result = subprocess.run(
        ["git", "log", "-1", "--format=%cI", "--", str(relative)],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if commit_result.returncode or not commit_result.stdout.strip():
        raise WalkForwardError(f"{path.name} must be committed before final-holdout collection")
    return _utc(commit_result.stdout.strip(), f"{path.name} commit timestamp")


def validate_plan(plan: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("plan_schema") != "VELTRIX_XAUUSD_WALK_FORWARD_PLAN_V1":
        raise WalkForwardError("unsupported walk-forward plan schema")
    if plan.get("canonical_symbol") != "XAUUSD" or plan.get("account_mode") != "DEMO":
        raise WalkForwardError("walk-forward plan must be Exness DEMO XAUUSD only")
    if plan.get("execution_enabled") is not False or plan.get("live_trading_enabled") is not False:
        raise WalkForwardError("walk-forward plan cannot enable execution")
    registry_result = validate_registry(registry)
    development = plan.get("development_sessions")
    validation = plan.get("validation_sessions")
    holdout = plan.get("final_holdout_sessions")
    if not isinstance(development, list) or len(development) != 2:
        raise WalkForwardError("exactly two registered development sessions are required")
    if not isinstance(validation, list) or len(validation) < 2 or len(set(validation)) != len(validation):
        raise WalkForwardError("validation session IDs must be unique and non-empty")
    if not isinstance(holdout, list) or len(holdout) < 2 or len(set(holdout)) != len(holdout):
        raise WalkForwardError("final holdout session IDs must be unique and non-empty")
    ids = [item.get("session_id") for item in development] + validation + holdout
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise WalkForwardError("session IDs must be globally unique")
    expected = set(registry["known_development_data"]["source_sha256"])
    planned = {item.get("expected_sha256") for item in development}
    if planned != expected:
        raise WalkForwardError("development session hashes do not exactly match the frozen strategy registry")
    for item in development:
        for field in ("expected_sha256", "expected_manifest_sha256"):
            digest = item.get(field)
            if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
                raise WalkForwardError(f"{item['session_id']}: {field} must be a 64-character SHA-256")
        if isinstance(item.get("workflow_run_id"), bool) or not isinstance(item.get("workflow_run_id"), int) or item["workflow_run_id"] <= 0:
            raise WalkForwardError(f"{item['session_id']}: workflow_run_id must be positive")
        if isinstance(item.get("artifact_id"), bool) or not isinstance(item.get("artifact_id"), int) or item["artifact_id"] <= 0:
            raise WalkForwardError(f"{item['session_id']}: artifact_id must be positive")
    requirements = plan.get("collection_requirements", {})
    if requirements.get("purge_seconds_at_partition_boundaries") != 120:
        raise WalkForwardError("partition purge must cover the frozen 60-second lookback plus 60-second horizon")
    if requirements.get("one_open_position_per_candidate_configuration") is not True:
        raise WalkForwardError("single-position candidate simulation is mandatory")
    evaluation = plan.get("evaluation", {})
    if evaluation.get("holding_horizons_seconds") != [5, 15, 30, 60]:
        raise WalkForwardError("registered holding horizons changed")
    if evaluation.get("slippage_sensitivity_points_per_side") != [0, 1, 2, 5]:
        raise WalkForwardError("registered slippage sensitivity grid changed")
    if evaluation.get("commission_status") != "UNVERIFIED_REQUIRED_INPUT" or evaluation.get("net_performance_allowed") is not False:
        raise WalkForwardError("commission and net-performance lock changed")
    return {
        "status": "PASS",
        "plan_schema": plan["plan_schema"],
        "registry_sha256": registry_result["registry_sha256"],
        "development_session_ids": [item["session_id"] for item in development],
        "validation_session_ids": validation,
        "final_holdout_session_ids": holdout,
        "commission_status": evaluation["commission_status"],
        "net_performance_allowed": False,
    }


def _load_catalog(catalog: dict[str, Any], base_dir: Path) -> dict[str, dict[str, Any]]:
    items = catalog.get("sessions") if isinstance(catalog, dict) else None
    if not isinstance(items, list):
        raise WalkForwardError("session catalog must contain a sessions array")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise WalkForwardError("each catalog session must be an object")
        sid = item.get("session_id")
        if not isinstance(sid, str) or not sid or sid in result:
            raise WalkForwardError("catalog session IDs must be unique non-empty strings")
        csv_path = Path(item.get("csv", ""))
        manifest_path = Path(item.get("manifest", ""))
        if not csv_path.is_absolute():
            csv_path = (base_dir / csv_path).resolve()
        if not manifest_path.is_absolute():
            manifest_path = (base_dir / manifest_path).resolve()
        result[sid] = {"session_id": sid, "csv": csv_path, "manifest": manifest_path}
    return result


def _validate_selected_configurations(selected: list[Any], registry: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_horizons = set(registry["evaluation"]["holding_horizons_seconds"])
    candidates = {item["candidate_id"]: item for item in registry["candidates"]}
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in selected:
        if not isinstance(item, dict):
            raise WalkForwardError("each selected configuration must be an object")
        cid, params, horizon = item.get("candidate_id"), item.get("parameters"), item.get("horizon_seconds")
        if cid not in candidates or not isinstance(params, dict) or horizon not in allowed_horizons:
            raise WalkForwardError("selection-freeze contains an unregistered candidate, parameter set, or horizon")
        grid = candidates[cid]["parameter_grid"]
        if set(params) != set(grid) or any(params[key] not in grid[key] for key in grid):
            raise WalkForwardError("selection-freeze parameters are outside the preregistered finite grid")
        canonical_params = {
            key: next(value for value in grid[key] if value == params[key])
            for key in grid
        }
        signature = json.dumps({"candidate_id": cid, "parameters": canonical_params, "horizon_seconds": horizon},
                               sort_keys=True, separators=(",", ":"))
        if signature in seen:
            raise WalkForwardError("selection-freeze contains duplicate candidate configurations")
        seen.add(signature)
        normalized.append({"candidate_id": cid, "parameters": canonical_params, "horizon_seconds": horizon})
    if not normalized:
        raise WalkForwardError("selection-freeze must contain at least one configuration")
    return normalized


def _validate_selection_against_validation_report(
    selected: list[dict[str, Any]],
    validation_report: dict[str, Any],
) -> None:
    """Permit holdout selection only from independently cost-qualified validation rows."""
    if validation_report.get("commission_status") != "VERIFIED_FROM_EXNESS_ACCOUNT_SCHEDULE":
        raise WalkForwardError("validation report commission is not verified; selection freeze is blocked")
    if validation_report.get("net_performance_allowed") is not True:
        raise WalkForwardError("validation report does not permit net-performance decisions")
    candidates = validation_report.get("candidate_results")
    if not isinstance(candidates, list):
        raise WalkForwardError("validation report has no candidate result table")

    eligible: set[str] = set()
    for row in candidates:
        if not isinstance(row, dict):
            continue
        if row.get("sample_size_gate_passed") is not True:
            continue
        if row.get("net_validation_gate_passed") is not True:
            continue
        if row.get("candidate_approval") != "VALIDATION_ELIGIBLE_FOR_HOLDOUT":
            continue
        signature = json.dumps({
            "candidate_id": row.get("candidate_id"),
            "parameters": row.get("parameters"),
            "horizon_seconds": row.get("horizon_seconds"),
        }, sort_keys=True, separators=(",", ":"))
        eligible.add(signature)

    for item in selected:
        signature = json.dumps(item, sort_keys=True, separators=(",", ":"))
        if signature not in eligible:
            raise WalkForwardError(
                "selection-freeze may include only configurations that passed validation "
                "sample-size, net-return, and all registered benchmark gates"
            )


def assess_session_catalog(
    plan: dict[str, Any],
    registry: dict[str, Any],
    catalog: dict[str, Any],
    *,
    stage: str,
    base_dir: Path,
    selection_freeze: dict[str, Any] | None = None,
    selection_freeze_path: Path | None = None,
    validation_report_path: Path | None = None,
) -> dict[str, Any]:
    if stage not in ("validation", "holdout"):
        raise WalkForwardError("stage must be validation or holdout")
    plan_result = validate_plan(plan, registry)
    supplied = _load_catalog(catalog, base_dir)
    development = {item["session_id"]: item for item in plan["development_sessions"]}
    validation_ids = list(plan["validation_sessions"])
    holdout_ids = list(plan["final_holdout_sessions"])
    allowed = set(development) | set(validation_ids)
    if stage == "holdout":
        allowed |= set(holdout_ids)
    unexpected = sorted(set(supplied) - allowed)
    if unexpected:
        raise WalkForwardError(f"catalog contains sessions outside the requested stage: {unexpected}")
    required = set(development) | set(validation_ids)
    if stage == "holdout":
        required |= set(holdout_ids)
    missing = sorted(required - set(supplied))
    if missing:
        return {
            "status": "BLOCKED_INSUFFICIENT_DATA",
            "stage": stage,
            "missing_session_ids": missing,
            "provided_session_ids": sorted(supplied),
            "validation_sessions_required": len(validation_ids),
            "holdout_sessions_required": len(holdout_ids),
            "registry_sha256": plan_result["registry_sha256"],
            "commission_status": plan["evaluation"]["commission_status"],
            "net_performance_allowed": False,
            "candidate_scoring_performed": False,
            "limitations": ["Missing chronological sessions; no candidate ranking or holdout scoring was performed."],
        }

    if stage == "holdout":
        if not isinstance(selection_freeze, dict):
            raise WalkForwardError("holdout scoring requires a committed validation selection-freeze record")
        required_fields = plan["selection_freeze_contract"]["required_fields"]
        if any(field not in selection_freeze for field in required_fields):
            raise WalkForwardError("selection-freeze record is incomplete")
        if selection_freeze.get("registry_sha256") != plan_result["registry_sha256"]:
            raise WalkForwardError("selection-freeze registry hash does not match the frozen registry")
        if selection_freeze_path is None or validation_report_path is None:
            raise WalkForwardError("selection-freeze and validation-report files are required for holdout scoring")
        try:
            validation_report = json.loads(validation_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WalkForwardError("validation report is unreadable") from exc
        if validation_report.get("status") != "RESEARCH_EVALUATION_COMPLETE" or validation_report.get("stage") != "validation":
            raise WalkForwardError("holdout requires a completed validation-stage report")
        if validation_report.get("registry_sha256") != plan_result["registry_sha256"]:
            raise WalkForwardError("validation report does not match the frozen strategy registry")
        if selection_freeze.get("selection_rule_id") != plan["selection_freeze_contract"]["selection_rule_id"]:
            raise WalkForwardError("selection-freeze rule does not match the preregistered rule")
        selected = selection_freeze.get("selected_candidate_configurations")
        if not isinstance(selected, list) or not selected:
            raise WalkForwardError("selection-freeze must select at least one validation configuration")
        if selection_freeze.get("validation_report_sha256") != _sha256(validation_report_path):
            raise WalkForwardError("selection-freeze does not bind to the exact validation report")
        freeze_time = _utc(selection_freeze.get("frozen_utc"), "selection_freeze.frozen_utc")
        validation_report_commit = _git_commit_utc(validation_report_path, base_dir)
        selection_freeze_commit = _git_commit_utc(selection_freeze_path, base_dir)
        if validation_report_commit > selection_freeze_commit:
            raise WalkForwardError("selection-freeze commit must be at or after the validation-report commit")
        if freeze_time < validation_report_commit or freeze_time > selection_freeze_commit:
            raise WalkForwardError("selection-freeze timestamp must fall between validation-report and freeze commits")
        earliest_holdout_start = min(
            _utc(json.loads(item["manifest"].read_text(encoding="utf-8")).get("collection_started_utc"),
                 f"{item['session_id']}.collection_started_utc")
            for sid, item in supplied.items() if sid in holdout_ids
        )
        if selection_freeze_commit >= earliest_holdout_start:
            raise WalkForwardError("selection-freeze commit must precede every final-holdout collection")
        try:
            on_disk_freeze = json.loads(selection_freeze_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WalkForwardError("selection-freeze file is unreadable") from exc
        if on_disk_freeze != selection_freeze:
            raise WalkForwardError("selection-freeze object differs from the committed file")
        selected_configurations = _validate_selected_configurations(selected, registry)
        _validate_selection_against_validation_report(selected_configurations, validation_report)

    expected_ids = set(development) | set(validation_ids)
    if stage == "holdout":
        expected_ids |= set(holdout_ids)
    sessions: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    intervals: list[tuple[datetime, datetime, str, str]] = []
    for sid in sorted(expected_ids):
        item = supplied[sid]
        profile = profile_dataset(item["csv"], item["manifest"])
        if profile.get("status") != "PASS":
            raise WalkForwardError(f"{sid}: dataset profile is not PASS")
        manifest = json.loads(item["manifest"].read_text(encoding="utf-8"))
        if sid not in development and manifest.get("session_id") != sid:
            raise WalkForwardError(f"{sid}: validation manifest session_id does not match the preregistered ID")
        if sid in development:
            expected_manifest = development[sid]
            if expected_manifest.get("expected_manifest_sha256") and _sha256(item["manifest"]) != expected_manifest["expected_manifest_sha256"]:
                raise WalkForwardError(f"{sid}: development manifest hash differs from the preregistered manifest")
            for field in ("collection_started_utc", "collection_ended_utc", "duration_seconds"):
                if manifest.get(field) != expected_manifest.get(field):
                    raise WalkForwardError(f"{sid}: development manifest {field} differs from the preregistered value")
        if manifest.get("account_mode") != "DEMO" or manifest.get("trading_enabled") is not False or manifest.get("dll_imports_enabled") is not False:
            raise WalkForwardError(f"{sid}: source manifest must prove read-only DEMO collection")
        specs = manifest.get("instrument_specs", {})
        if set(specs) != {"XAUUSD"}:
            raise WalkForwardError(f"{sid}: manifest must contain XAUUSD only")
        spec = specs["XAUUSD"]
        if spec.get("currency_base") != "XAU" or spec.get("currency_profit") != "USD":
            raise WalkForwardError(f"{sid}: broker contract metadata is not verified XAUUSD")
        if profile["sha256"] in seen_hashes:
            raise WalkForwardError("duplicate source dataset hashes are not independent sessions")
        seen_hashes.add(profile["sha256"])
        start = _utc(manifest.get("collection_started_utc"), f"{sid}.collection_started_utc")
        end = _utc(manifest.get("collection_ended_utc"), f"{sid}.collection_ended_utc")
        duration = manifest.get("duration_seconds")
        if end <= start or manifest.get("duration_clock") != "monotonic" or isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration):
            raise WalkForwardError(f"{sid}: invalid collection interval or monotonic duration")
        if duration < plan["collection_requirements"]["minimum_session_duration_seconds"]:
            raise WalkForwardError(f"{sid}: session is shorter than the preregistered minimum")
        role = "development" if sid in development else ("validation" if sid in validation_ids else "final_holdout")
        if role == "development" and profile["sha256"] != development[sid]["expected_sha256"]:
            raise WalkForwardError(f"{sid}: development hash differs from the preregistered source")
        if role != "development" and profile["sha256"] in registry["known_development_data"]["source_sha256"]:
            raise WalkForwardError(f"{sid}: inspected development data cannot be promoted to {role}")
        intervals.append((start, end, sid, role))
        sessions.append({
            "session_id": sid, "partition": role, "sha256": profile["sha256"],
            "records": profile["records"], "started_utc": start.isoformat(),
            "ended_utc": end.isoformat(), "duration_seconds": float(duration),
            "csv": item["csv"], "manifest": item["manifest"],
        })

    ordered = sorted(intervals, key=lambda row: row[0])
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] < previous[1]:
            raise WalkForwardError(f"overlapping sessions: {previous[2]} and {current[2]}")
        if current[3] != previous[3]:
            purge_seconds = plan["collection_requirements"]["purge_seconds_at_partition_boundaries"]
            if (current[0] - previous[1]).total_seconds() < purge_seconds:
                raise WalkForwardError("partition boundary is shorter than the preregistered purge interval")
        if current[3] == "validation" and previous[3] == "final_holdout":
            raise WalkForwardError("validation sessions cannot occur after final holdout")
        if current[3] == "final_holdout" and previous[3] == "validation":
            continue
        rank = {"development": 0, "validation": 1, "final_holdout": 2}
        if rank[current[3]] < rank[previous[3]]:
            raise WalkForwardError("session partitions are not strictly chronological")

    for role in ("validation", "final_holdout"):
        role_sessions = [row for row in sessions if row["partition"] == role]
        if not role_sessions:
            continue
        dates = {row["started_utc"][:10] for row in role_sessions}
        minimum_key = "minimum_holdout_distinct_dates" if role == "final_holdout" else f"minimum_{role}_distinct_dates"
        minimum = plan["collection_requirements"][minimum_key]
        if len(dates) < minimum:
            return {
                "status": "BLOCKED_INSUFFICIENT_DISTINCT_DATES",
                "stage": stage,
                "partition": role,
                "observed_dates": sorted(dates),
                "required_distinct_dates": minimum,
                "candidate_scoring_performed": False,
                "commission_status": plan["evaluation"]["commission_status"],
            }
    if stage == "validation":
        target = [row for row in sessions if row["partition"] == "validation"]
    else:
        target = [row for row in sessions if row["partition"] == "final_holdout"]
    return {
        "status": "READY_FOR_RESEARCH_EVALUATION",
        "stage": stage,
        "registry_sha256": plan_result["registry_sha256"],
        "sessions": sessions,
        "evaluation_sessions": target,
        "selection_freeze_sha256": _sha256(selection_freeze_path) if selection_freeze_path else None,
        "selected_candidate_configurations": selected_configurations if stage == "holdout" else None,
        "plan": plan,
        "commission_status": plan["evaluation"]["commission_status"],
        "net_performance_allowed": False,
        "research_only": True,
    }


def _group_key(event: dict[str, Any]) -> tuple[str, str, int]:
    params = json.dumps(event.get("parameters", {}), sort_keys=True, separators=(",", ":"))
    return event["candidate_id"], params, int(event["horizon_seconds"])


def _session_cluster_ci(session_means: list[float]) -> dict[str, float | None]:
    if len(session_means) < 2:
        return {"lower_95": None, "upper_95": None}
    rng = random.Random(20261113)
    samples: list[float] = []
    for _ in range(2000):
        picked = [session_means[rng.randrange(len(session_means))] for _ in session_means]
        samples.append(statistics.mean(picked))
    samples.sort()
    return {
        "lower_95": round(samples[int(0.025 * (len(samples) - 1))], 8),
        "upper_95": round(samples[int(0.975 * (len(samples) - 1))], 8),
    }


def _apply_verified_commission(outcome: dict[str, Any], verified: dict[str, Any]) -> None:
    """Attach round-turn commission to every replay slippage scenario exactly once."""
    if outcome.get("status") != "OUTCOME_AVAILABLE":
        return
    entry_price = outcome.get("entry_executable_price")
    if isinstance(entry_price, bool) or not isinstance(entry_price, (int, float)) or not math.isfinite(entry_price) or entry_price <= 0:
        raise WalkForwardError("commission evaluation requires a valid executable entry price")
    for scenario in outcome.get("slippage_sensitivity", []):
        scenario["net_after_commission_bps"] = net_return_bps(
            scenario["return_before_commission_bps"],
            verified,
            entry_price_usd_per_oz=float(entry_price),
            lot_size=1.0,
        )
    outcome["commission_status"] = "VERIFIED_FROM_EXNESS_ACCOUNT_SCHEDULE"


def _summarize_group(
    outcomes_by_session: dict[str, list[dict[str, Any]]],
    slippage_grid: list[int],
    *,
    commission_verified: bool = False,
) -> dict[str, Any]:
    sessions = {}
    all_returns: dict[int, list[float]] = {points: [] for points in slippage_grid}
    session_means: dict[int, list[float]] = {points: [] for points in slippage_grid}
    all_net_returns: dict[int, list[float]] = {points: [] for points in slippage_grid}
    session_net_means: dict[int, list[float]] = {points: [] for points in slippage_grid}
    total_skipped = 0
    total_timeouts = 0
    for sid, outcomes in sorted(outcomes_by_session.items()):
        accepted: list[dict[str, Any]] = []
        next_free = 0
        unresolved = False
        for outcome in sorted(outcomes, key=lambda row: row["signal_window_end_msc"]):
            if unresolved:
                total_skipped += 1
                continue
            if outcome["status"] == "ENTRY_QUOTE_TIMEOUT":
                total_timeouts += 1
                continue
            if outcome["status"] == "EXIT_QUOTE_TIMEOUT":
                total_timeouts += 1
                if outcome.get("entry_time_msc"):
                    unresolved = True
                continue
            if outcome["status"] != "OUTCOME_AVAILABLE":
                continue
            if outcome["entry_time_msc"] <= next_free:
                total_skipped += 1
                continue
            next_free = outcome["exit_time_msc"]
            accepted.append(outcome)
        scenario = {}
        for points in slippage_grid:
            returns = []
            net_returns = []
            for outcome in accepted:
                item = next(x for x in outcome["slippage_sensitivity"] if x["slippage_points_per_side"] == points)
                returns.append(float(item["return_before_commission_bps"]))
                if commission_verified:
                    net_value = item.get("net_after_commission_bps")
                    if isinstance(net_value, bool) or not isinstance(net_value, (int, float)) or not math.isfinite(net_value):
                        raise WalkForwardError("verified commission is missing from an available replay outcome")
                    net_returns.append(float(net_value))
            all_returns[points].extend(returns)
            if returns:
                session_means[points].append(statistics.mean(returns))
            if commission_verified:
                all_net_returns[points].extend(net_returns)
                if net_returns:
                    session_net_means[points].append(statistics.mean(net_returns))
            scenario[str(points)] = {
                "outcomes": len(returns),
                "mean_return_before_commission_bps": round(statistics.mean(returns), 8) if returns else None,
                "median_return_before_commission_bps": round(statistics.median(returns), 8) if returns else None,
                "win_rate_before_commission": round(sum(value > 0 for value in returns) / len(returns), 8) if returns else None,
                "mean_net_after_commission_bps": round(statistics.mean(net_returns), 8) if net_returns else None,
                "median_net_after_commission_bps": round(statistics.median(net_returns), 8) if net_returns else None,
                "win_rate_after_commission": round(sum(value > 0 for value in net_returns) / len(net_returns), 8) if net_returns else None,
            }
        sessions[sid] = {
            "available_outcomes_after_single_position_filter": len(accepted),
            "skipped_overlapping_or_unresolved": sum(1 for _ in outcomes) - len(accepted) - sum(1 for x in outcomes if x["status"] == "ENTRY_QUOTE_TIMEOUT") - sum(1 for x in outcomes if x["status"] == "EXIT_QUOTE_TIMEOUT"),
            "cost_sensitivity": scenario,
        }
    aggregate = {}
    net_aggregate = {}
    for points in slippage_grid:
        values = all_returns[points]
        net_values = all_net_returns[points]
        aggregate[str(points)] = {
            "outcomes": len(values),
            "mean_return_before_commission_bps": round(statistics.mean(values), 8) if values else None,
            "median_return_before_commission_bps": round(statistics.median(values), 8) if values else None,
            "win_rate_before_commission": round(sum(value > 0 for value in values) / len(values), 8) if values else None,
            "session_clustered_mean_ci_95": _session_cluster_ci(session_means[points]),
            "mean_net_after_commission_bps": round(statistics.mean(net_values), 8) if net_values else None,
            "median_net_after_commission_bps": round(statistics.median(net_values), 8) if net_values else None,
            "win_rate_after_commission": round(sum(value > 0 for value in net_values) / len(net_values), 8) if net_values else None,
            "session_clustered_net_mean_ci_95": _session_cluster_ci(session_net_means[points]) if commission_verified else {"lower_95": None, "upper_95": None},
        }
        if commission_verified:
            net_aggregate[str(points)] = {
                "outcomes": len(net_values),
                "mean_net_after_commission_bps": aggregate[str(points)]["mean_net_after_commission_bps"],
                "session_clustered_net_mean_ci_95": aggregate[str(points)]["session_clustered_net_mean_ci_95"],
            }
    return {
        "sessions": sessions,
        "aggregate_cost_sensitivity": aggregate,
        "commission_status": "VERIFIED_FROM_EXNESS_ACCOUNT_SCHEDULE" if commission_verified else "UNVERIFIED_REQUIRED_INPUT",
        "net_after_commission": net_aggregate if commission_verified else None,
        "candidate_approval": "NOT_APPROVED",
        "total_timeouts": total_timeouts,
        "total_skipped": total_skipped,
    }


def evaluate_partition(
    ready: dict[str, Any],
    registry: dict[str, Any],
    verified_commission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if ready.get("status") != "READY_FOR_RESEARCH_EVALUATION":
        return ready
    commission_verified = verified_commission is not None
    slippage_grid = registry["evaluation"]["additional_costs"]["slippage_sensitivity_points_per_side"]
    candidate_results: dict[tuple[str, str, int], dict[str, list[dict[str, Any]]]] = {}
    benchmark_results: dict[tuple[str, int], dict[str, list[dict[str, Any]]]] = {}
    for session in ready["evaluation_sessions"]:
        features = build_features(session["csv"], session["manifest"], window_seconds=5)
        candidate = generate_candidate_events(features, registry)
        ticks, profile = load_verified_ticks(session["csv"], session["manifest"])
        manifest = json.loads(session["manifest"].read_text(encoding="utf-8"))
        events = candidate["events"]
        if ready["stage"] == "holdout":
            selected_signatures = {
                json.dumps(item, sort_keys=True, separators=(",", ":"))
                for item in ready["selected_candidate_configurations"]
            }
            events = [
                event for event in events
                if json.dumps({
                    "candidate_id": event["candidate_id"],
                    "parameters": event["parameters"],
                    "horizon_seconds": event["horizon_seconds"],
                }, sort_keys=True, separators=(",", ":")) in selected_signatures
            ]
        replay = replay_events(ticks, events, manifest, registry, source_profile=profile)
        for event, outcome in zip(events, replay["outcomes"]):
            if commission_verified:
                _apply_verified_commission(outcome, verified_commission)
            key = _group_key(event)
            candidate_results.setdefault(key, {}).setdefault(session["session_id"], []).append(outcome)

        # Directional benchmarks use the same completed windows, quote convention,
        # horizon, slippage grid, commission, and one-position constraint as candidates.
        for index, row in enumerate(features["features"][:-1]):
            stamp = int(datetime.fromisoformat(row["window_start_utc"].replace("Z", "+00:00")).timestamp() * 1000) + 5000
            for horizon in registry["evaluation"]["holding_horizons_seconds"]:
                for direction in ("long", "short"):
                    event = {
                        "signal_id": f"BENCHMARK_{direction}_{index}_{horizon}",
                        "candidate_id": registry["candidates"][0]["candidate_id"],
                        "signal_window_end_msc": stamp,
                        "direction": direction,
                        "horizon_seconds": horizon,
                    }
                    outcome = evaluate_event(ticks, event, point_size=float(manifest["instrument_specs"]["XAUUSD"]["point"]),
                                             slippage_grid=slippage_grid,
                                             entry_max_wait_ms=registry["evaluation"]["entry_max_wait_seconds"] * 1000,
                                             exit_tolerance_ms=2000)
                    if commission_verified:
                        _apply_verified_commission(outcome, verified_commission)
                    benchmark_results.setdefault((direction, horizon), {}).setdefault(session["session_id"], []).append(outcome)

    candidate_report = []
    for (candidate_id, params, horizon), by_session in sorted(candidate_results.items()):
        summary = _summarize_group(by_session, slippage_grid, commission_verified=commission_verified)
        required_outcomes = (
            ready["plan"]["collection_requirements"]["minimum_holdout_outcomes_per_configuration_horizon"]
            if ready["stage"] == "holdout"
            else ready["plan"]["collection_requirements"]["minimum_validation_outcomes_per_configuration_horizon"]
        )
        observed_outcomes = summary["aggregate_cost_sensitivity"]["0"]["outcomes"]
        candidate_report.append({
            "candidate_id": candidate_id,
            "parameters": json.loads(params),
            "horizon_seconds": horizon,
            **summary,
            "minimum_outcomes_required": required_outcomes,
            "sample_size_gate_passed": observed_outcomes >= required_outcomes,
            "net_validation_gate_passed": False,
        })
    benchmarks = []
    for (direction, horizon), by_session in sorted(benchmark_results.items()):
        benchmarks.append({
            "benchmark": "ALWAYS_" + direction.upper(),
            "horizon_seconds": horizon,
            **_summarize_group(by_session, slippage_grid, commission_verified=commission_verified),
        })
    benchmark_lookup = {
        (item["benchmark"], item["horizon_seconds"]): item
        for item in benchmarks
    }
    for candidate in candidate_report:
        relative = {}
        for points in slippage_grid:
            scenario_key = str(points)
            candidate_means = {
                sid: row["cost_sensitivity"][scenario_key]["mean_return_before_commission_bps"]
                for sid, row in candidate["sessions"].items()
                if row["cost_sensitivity"][scenario_key]["mean_return_before_commission_bps"] is not None
            }
            candidate_net_means = {
                sid: row["cost_sensitivity"][scenario_key]["mean_net_after_commission_bps"]
                for sid, row in candidate["sessions"].items()
                if row["cost_sensitivity"][scenario_key]["mean_net_after_commission_bps"] is not None
            }
            comparisons = {}
            for baseline_name in ("NO_TRADE", "ALWAYS_LONG", "ALWAYS_SHORT"):
                if baseline_name == "NO_TRADE":
                    baseline_means = {sid: 0.0 for sid in candidate_means}
                    baseline_net_means = {sid: 0.0 for sid in candidate_net_means}
                else:
                    baseline = benchmark_lookup.get((baseline_name, candidate["horizon_seconds"]))
                    baseline_means = {} if baseline is None else {
                        sid: row["cost_sensitivity"][scenario_key]["mean_return_before_commission_bps"]
                        for sid, row in baseline["sessions"].items()
                        if row["cost_sensitivity"][scenario_key]["mean_return_before_commission_bps"] is not None
                    }
                    baseline_net_means = {} if baseline is None else {
                        sid: row["cost_sensitivity"][scenario_key]["mean_net_after_commission_bps"]
                        for sid, row in baseline["sessions"].items()
                        if row["cost_sensitivity"][scenario_key]["mean_net_after_commission_bps"] is not None
                    }
                common = sorted(set(candidate_means) & set(baseline_means))
                differences = [candidate_means[sid] - baseline_means[sid] for sid in common]
                ci = _session_cluster_ci(differences)
                comparison = {
                    "sessions_compared": len(common),
                    "mean_difference_before_commission_bps": round(statistics.mean(differences), 8) if differences else None,
                    "session_clustered_difference_ci_95": ci,
                    "gross_after_slippage_outperformance": bool(ci["lower_95"] is not None and ci["lower_95"] > 0),
                    "net_comparison_status": "VERIFIED" if commission_verified else "BLOCKED_COMMISSION_UNVERIFIED",
                    "net_outperformance": False,
                    "mean_difference_after_commission_bps": None,
                    "session_clustered_net_difference_ci_95": {"lower_95": None, "upper_95": None},
                }
                if commission_verified:
                    net_common = sorted(set(candidate_net_means) & set(baseline_net_means))
                    net_differences = [candidate_net_means[sid] - baseline_net_means[sid] for sid in net_common]
                    net_ci = _session_cluster_ci(net_differences)
                    comparison.update({
                        "net_sessions_compared": len(net_common),
                        "mean_difference_after_commission_bps": round(statistics.mean(net_differences), 8) if net_differences else None,
                        "session_clustered_net_difference_ci_95": net_ci,
                        "net_outperformance": bool(net_ci["lower_95"] is not None and net_ci["lower_95"] > 0),
                    })
                comparisons[baseline_name] = comparison
            relative[scenario_key] = comparisons
        candidate["relative_benchmark_comparison"] = relative
        if commission_verified and ready["stage"] == "validation":
            scenario_passes = []
            for points in slippage_grid:
                key = str(points)
                aggregate = candidate["aggregate_cost_sensitivity"][key]
                ci = aggregate["session_clustered_net_mean_ci_95"]
                positive_mean = aggregate["mean_net_after_commission_bps"] is not None and aggregate["mean_net_after_commission_bps"] > 0
                positive_ci = ci["lower_95"] is not None and ci["lower_95"] > 0
                benchmark_passes = all(
                    relative[key][name]["net_outperformance"]
                    for name in ("NO_TRADE", "ALWAYS_LONG", "ALWAYS_SHORT")
                )
                scenario_passes.append(positive_mean and positive_ci and benchmark_passes)
            candidate["net_validation_gate_passed"] = bool(scenario_passes and all(scenario_passes))
            if candidate["sample_size_gate_passed"] and candidate["net_validation_gate_passed"]:
                candidate["candidate_approval"] = "VALIDATION_ELIGIBLE_FOR_HOLDOUT"

    evidence_summary = None
    if commission_verified:
        evidence_summary = {
            "status": verified_commission["status"],
            "broker_symbol": verified_commission["broker_symbol"],
            "account_mode": verified_commission["account_mode"],
            "contract_size_oz_per_lot": verified_commission["contract_size_oz_per_lot"],
            "commission_usd_per_lot_per_side": verified_commission["commission_usd_per_lot_per_side"],
            "source_sha256": verified_commission["source_sha256"],
            "source_reference": verified_commission["source_reference"],
            "verification_reference": verified_commission["verification_reference"],
            "effective_from_utc": verified_commission["effective_from_utc"],
            "effective_to_utc": verified_commission["effective_to_utc"],
        }
    return {
        "status": "RESEARCH_EVALUATION_COMPLETE",
        "stage": ready["stage"],
        "research_only": True,
        "canonical_symbol": "XAUUSD",
        "registry_sha256": ready["registry_sha256"],
        "partition_sessions": [
            {"session_id": row["session_id"], "sha256": row["sha256"], "started_utc": row["started_utc"]}
            for row in ready["evaluation_sessions"]
        ],
        "candidate_results": candidate_report,
        "benchmarks": benchmarks,
        "no_trade_benchmark": {
            "mean_return_before_commission_bps": 0.0,
            "mean_net_after_commission_bps": 0.0 if commission_verified else None,
        },
        "commission_status": "VERIFIED_FROM_EXNESS_ACCOUNT_SCHEDULE" if commission_verified else "UNVERIFIED_REQUIRED_INPUT",
        "commission_evidence": evidence_summary,
        "net_performance_allowed": commission_verified,
        "holdout_eligible": ready["stage"] == "holdout" and commission_verified,
        "candidate_approval": "NOT_APPROVED",
        "limitations": [
            "All outcomes are theoretical bid/ask quote marks, not broker fills.",
            "Spread is included once; slippage is a sensitivity assumption, not measured execution slippage.",
            "Each candidate configuration is simulated with at most one open position; unresolved exit timeouts block later signals in that session.",
            "Confidence intervals resample independent session clusters, not overlapping tick rows.",
            "Net validation eligibility requires positive net mean, positive session-clustered 95% lower bound, and outperformance versus all three registered benchmarks at every registered slippage level.",
            "Research completion does not approve a candidate or authorize execution.",
        ] + ([] if commission_verified else ["Commission is unverified; net P/L remains null and no candidate can be validation-eligible."]),
    }



def run_walk_forward(
    plan: dict[str, Any],
    registry: dict[str, Any],
    catalog: dict[str, Any],
    *,
    stage: str,
    base_dir: Path,
    selection_freeze: dict[str, Any] | None = None,
    selection_freeze_path: Path | None = None,
    validation_report_path: Path | None = None,
    commission_evidence: dict[str, Any] | None = None,
    commission_source_artifact_path: Path | None = None,
    commission_verification_artifact_path: Path | None = None,
    commission_verification_time_utc: str | None = None,
) -> dict[str, Any]:
    if stage == "holdout" and (
        commission_evidence is None
        or commission_source_artifact_path is None
        or commission_verification_artifact_path is None
    ):
        return {
            "status": "BLOCKED_COMMISSION_UNVERIFIED",
            "stage": stage,
            "candidate_scoring_performed": False,
            "holdout_opened": False,
            "commission_status": "UNVERIFIED_REQUIRED_INPUT",
            "net_performance_allowed": False,
            "required_manual_evidence": "Applicable Exness DEMO XAUUSD commission schedule, original source artifact, and separately hashed independent verification artifact.",
        }
    supplied_commission_inputs = (
        commission_evidence is not None,
        commission_source_artifact_path is not None,
        commission_verification_artifact_path is not None,
    )
    if any(supplied_commission_inputs) and not all(supplied_commission_inputs):
        raise WalkForwardError("commission evidence JSON, original source artifact, and independent verification artifact must be supplied together")
    ready = assess_session_catalog(plan, registry, catalog, stage=stage, base_dir=base_dir,
                                   selection_freeze=selection_freeze,
                                   selection_freeze_path=selection_freeze_path,
                                   validation_report_path=validation_report_path)
    if ready.get("status") != "READY_FOR_RESEARCH_EVALUATION":
        return ready

    verified_commission = None
    if commission_evidence is not None:
        evaluation_sessions = ready["evaluation_sessions"]
        if not evaluation_sessions:
            raise WalkForwardError("commission validation requires at least one evaluation session")
        specs = []
        starts = []
        ends = []
        for session in evaluation_sessions:
            manifest = json.loads(session["manifest"].read_text(encoding="utf-8"))
            spec = manifest.get("instrument_specs", {}).get("XAUUSD", {})
            broker_symbol = spec.get("broker_symbol")
            contract_size = spec.get("trade_contract_size")
            if not isinstance(broker_symbol, str) or not broker_symbol:
                raise WalkForwardError("evaluation manifest is missing the exact broker symbol")
            if isinstance(contract_size, bool) or not isinstance(contract_size, (int, float)) or not math.isfinite(contract_size) or contract_size <= 0:
                raise WalkForwardError("evaluation manifest is missing a valid broker contract size")
            if spec.get("currency_profit") != "USD":
                raise WalkForwardError("evaluation manifest profit currency is not USD")
            specs.append((broker_symbol, float(contract_size)))
            starts.append(_utc(manifest.get("collection_started_utc"), "collection_started_utc"))
            ends.append(_utc(manifest.get("collection_ended_utc"), "collection_ended_utc"))
        if len({item[0] for item in specs}) != 1 or len({item[1] for item in specs}) != 1:
            raise WalkForwardError("evaluation sessions do not share one stable XAUUSD broker contract")
        broker_symbol, manifest_contract_size = specs[0]
        try:
            verified_commission = validate_commission_evidence(
                commission_evidence,
                broker_symbol=broker_symbol,
                account_mode="DEMO",
                evaluation_time_utc=max(ends).isoformat(),
                evaluation_start_utc=min(starts).isoformat(),
                evaluation_end_utc=max(ends).isoformat(),
                verification_time_utc=commission_verification_time_utc,
                source_artifact_path=commission_source_artifact_path,
                verification_artifact_path=commission_verification_artifact_path,
            )
        except CommissionEvidenceError as exc:
            raise WalkForwardError(f"commission evidence rejected: {exc}") from exc
        if not math.isclose(
            verified_commission["contract_size_oz_per_lot"],
            manifest_contract_size,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise WalkForwardError("commission evidence contract size does not match the collected XAUUSD contract")

    return evaluate_partition(ready, registry, verified_commission)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=Path("research/xauusd_walk_forward_plan_v1.json"))
    parser.add_argument("--registry", type=Path, default=Path("research/xauusd_strategy_registry_v1.json"))
    parser.add_argument("--stage", choices=("validation", "holdout"), default="validation")
    parser.add_argument("--selection-freeze", type=Path)
    parser.add_argument("--validation-report", type=Path)
    parser.add_argument("--commission-evidence", type=Path)
    parser.add_argument("--commission-source-artifact", type=Path)
    parser.add_argument("--commission-verification-artifact", type=Path)
    parser.add_argument("--commission-verification-time-utc")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        freeze = json.loads(args.selection_freeze.read_text(encoding="utf-8")) if args.selection_freeze else None
        commission = json.loads(args.commission_evidence.read_text(encoding="utf-8")) if args.commission_evidence else None
        result = run_walk_forward(plan, registry, catalog, stage=args.stage,
                                  base_dir=args.catalog.parent,
                                  selection_freeze=freeze,
                                  selection_freeze_path=args.selection_freeze,
                                  validation_report_path=args.validation_report,
                                  commission_evidence=commission,
                                  commission_source_artifact_path=args.commission_source_artifact,
                                  commission_verification_artifact_path=args.commission_verification_artifact,
                                  commission_verification_time_utc=args.commission_verification_time_utc)
    except (OSError, json.JSONDecodeError, ProfileError, CandidateError, RegistryError, ReplayError, WalkForwardError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"WALK-FORWARD FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
