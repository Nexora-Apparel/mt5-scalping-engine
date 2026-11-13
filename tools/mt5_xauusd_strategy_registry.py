"""Fail-closed validator for the frozen XAUUSD strategy hypothesis registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "VELTRIX_XAUUSD_STRATEGY_REGISTRY_V1"
REQUIRED_HORIZONS = [5, 15, 30, 60]
REQUIRED_CANDIDATES = {
    "XAU_MOMENTUM_CONTINUATION_V1",
    "XAU_MEAN_REVERSION_V1",
    "XAU_VOLATILITY_BREAKOUT_V1",
}


class RegistryError(ValueError):
    """Raised when the strategy registry violates its frozen research contract."""


def _positive_grid(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise RegistryError(f"{field} must be a non-empty list")
    if len(set(value)) != len(value):
        raise RegistryError(f"{field} must not contain duplicates")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise RegistryError(f"{field} must contain finite positive numbers")
        if not math.isfinite(float(item)) or item <= 0:
            raise RegistryError(f"{field} must contain finite positive numbers")


def validate_registry(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise RegistryError("registry must be a JSON object")
    if data.get("registry_schema") != SCHEMA or data.get("registry_version") != 1:
        raise RegistryError("unsupported registry schema or version")
    if data.get("status") != "PREREGISTERED_RESEARCH_ONLY":
        raise RegistryError("registry must remain preregistered and research-only")
    if data.get("canonical_symbol") != "XAUUSD":
        raise RegistryError("canonical_symbol must be XAUUSD")
    if data.get("account_mode") != "DEMO" or data.get("broker") != "Exness":
        raise RegistryError("only the Exness DEMO research scope is permitted")
    if data.get("research_only") is not True:
        raise RegistryError("research_only must be true")
    if data.get("order_execution_enabled") is not False or data.get("live_trading_enabled") is not False:
        raise RegistryError("order execution and live trading must remain disabled")

    contract = data.get("data_contract")
    if not isinstance(contract, dict) or contract.get("feature_window_seconds") != 5:
        raise RegistryError("data contract must use five-second feature windows")
    if contract.get("traded_volume_available") is not False or contract.get("order_book_depth_available") is not False:
        raise RegistryError("unavailable traded volume or depth must not be claimed")

    development = data.get("known_development_data")
    if not isinstance(development, dict) or development.get("holdout_eligible") is not False:
        raise RegistryError("previously inspected development sessions cannot be holdout data")
    hashes = development.get("source_sha256")
    if not isinstance(hashes, list) or len(hashes) < 2 or len(set(hashes)) != len(hashes):
        raise RegistryError("development sessions must have distinct source hashes")
    if any(not isinstance(x, str) or len(x) != 64 or any(c not in "0123456789abcdef" for c in x) for x in hashes):
        raise RegistryError("development source hashes must be lowercase SHA-256 values")

    evaluation = data.get("evaluation")
    if not isinstance(evaluation, dict) or evaluation.get("holding_horizons_seconds") != REQUIRED_HORIZONS:
        raise RegistryError("holding horizons must be exactly [5, 15, 30, 60] seconds")
    if evaluation.get("signal_entry") != "First valid quote strictly after the completed signal window end.":
        raise RegistryError("entry must occur strictly after the completed signal window")
    if evaluation.get("entry_max_wait_seconds") != 5 or evaluation.get("exit_quote") != (
        "First valid quote at or after entry_time + horizon, provided it is no more than 2 seconds late; otherwise outcome is missing."
    ):
        raise RegistryError("quote timing policy differs from the preregistered policy")
    convention = evaluation.get("executable_quote_convention", {})
    if convention.get("long_entry") != "Ask" or convention.get("long_exit") != "Bid":
        raise RegistryError("long outcomes must cross executable ask/bid quotes")
    if convention.get("short_entry") != "Bid" or convention.get("short_exit") != "Ask":
        raise RegistryError("short outcomes must cross executable bid/ask quotes")
    if convention.get("spread_treatment") != "Included once through executable bid/ask crossing; do not subtract spread a second time.":
        raise RegistryError("spread must be included exactly once")
    costs = evaluation.get("additional_costs", {})
    if costs.get("commission") != "UNVERIFIED_REQUIRED_INPUT":
        raise RegistryError("commission must remain explicitly unverified until sourced")
    if costs.get("slippage_sensitivity_points_per_side") != [0, 1, 2, 5]:
        raise RegistryError("slippage sensitivity grid changed")
    if evaluation.get("benchmark_set") != ["NO_TRADE", "ALWAYS_LONG", "ALWAYS_SHORT"]:
        raise RegistryError("required benchmark set changed")
    if evaluation.get("evaluation_is_not_execution") != "All fills are theoretical quote-crossed marks. No broker order is sent and no actual fill probability is inferred.":
        raise RegistryError("evaluation must not be represented as actual execution")

    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        raise RegistryError("candidates must be a list")
    ids = [item.get("candidate_id") for item in candidates if isinstance(item, dict)]
    if len(ids) != len(candidates) or len(ids) != len(set(ids)):
        raise RegistryError("candidate entries must be objects with unique IDs")
    if set(ids) != REQUIRED_CANDIDATES:
        raise RegistryError("candidate set differs from the preregistered three hypotheses")
    for item in candidates:
        if item.get("horizons_seconds") != REQUIRED_HORIZONS:
            raise RegistryError(f"{item['candidate_id']}: holding horizons changed")
        if not isinstance(item.get("falsifiable_hypothesis"), str) or len(item["falsifiable_hypothesis"]) < 40:
            raise RegistryError(f"{item['candidate_id']}: falsifiable hypothesis is missing")
        if not isinstance(item.get("signal_definition"), str) or not item["signal_definition"]:
            raise RegistryError(f"{item['candidate_id']}: signal definition is missing")
        if not isinstance(item.get("invalidation"), str) or not item["invalidation"]:
            raise RegistryError(f"{item['candidate_id']}: invalidation rules are missing")
        if not isinstance(item.get("exit"), str) or "Fixed holding horizon" not in item["exit"]:
            raise RegistryError(f"{item['candidate_id']}: exit must remain fixed-horizon")
        grid = item.get("parameter_grid")
        if not isinstance(grid, dict) or not grid:
            raise RegistryError(f"{item['candidate_id']}: parameter grid is missing")
        for name, values in grid.items():
            _positive_grid(values, f"{item['candidate_id']}.{name}")

    partition = data.get("data_partition_policy", {})
    if "untouched final holdout" not in partition.get("final_holdout", "").lower():
        raise RegistryError("an untouched chronological final holdout is required")
    controls = partition.get("leakage_controls", [])
    if not all(isinstance(x, str) and x for x in controls) or len(controls) < 5:
        raise RegistryError("chronological leakage controls are incomplete")
    decision = data.get("decision_policy", {})
    required_true = (
        "no_candidate_is_currently_approved",
        "no_parameter_tuning_on_holdout",
        "do_not_rank_by_gross_returns",
        "require_commission_verified",
        "require_spread_aware_executable_quote_outcomes",
        "require_chronological_out_of_sample_evidence",
        "no_execution_authorized",
    )
    if any(decision.get(key) is not True for key in required_true):
        raise RegistryError("candidate approval, cost, holdout, or execution safeguards changed")

    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "status": "PASS",
        "research_only": True,
        "registry_schema": SCHEMA,
        "registry_sha256": hashlib.sha256(canonical).hexdigest(),
        "candidate_count": len(candidates),
        "candidate_ids": sorted(ids),
        "holding_horizons_seconds": REQUIRED_HORIZONS,
        "order_execution_enabled": False,
        "live_trading_enabled": False,
        "commission_status": costs["commission"],
        "final_holdout_eligible_development_sessions": 0,
        "limitations": [
            "Registry validity is not evidence that any hypothesis has predictive power.",
            "Commission remains an unverified required input; net candidate evaluation is blocked until sourced.",
            "The two previously inspected development sessions are not eligible as an untouched holdout.",
            "All replay outcomes are theoretical bid/ask quote marks, not actual fills.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("research/xauusd_strategy_registry_v1.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.registry.read_text(encoding="utf-8"))
        result = validate_registry(data)
    except (OSError, json.JSONDecodeError, RegistryError) as exc:
        parser.exit(2, f"REGISTRY FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
