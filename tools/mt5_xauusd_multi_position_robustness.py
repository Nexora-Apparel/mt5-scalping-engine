"""Run isolated multi-position candidate/configuration robustness sweeps.

The harness replays each candidate and stop/target/horizon configuration
independently against identical XAUUSD DEMO quote data at 0/1/2/5 point
slippage per side. It reports gross diagnostics only: commission remains
unverified, net PnL remains unavailable, and no orders are submitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.mt5_xauusd_multi_position_simulator import (
    PortfolioSimulationError,
    PortfolioTick,
    simulate_portfolio,
)


SLIPPAGE_GRID = (0, 1, 2, 5)


class RobustnessEvaluationError(ValueError):
    """Raised when the robustness-sweep evidence is incomplete or invalid."""


def run_robustness_sweep(
    ticks: list[PortfolioTick],
    event_payload: dict[str, Any],
    broker_snapshot: dict[str, Any],
    risk_config: dict[str, Any],
    *,
    slippage_grid: tuple[int, ...] = SLIPPAGE_GRID,
) -> dict[str, Any]:
    if not isinstance(event_payload, dict) or event_payload.get("status") != "PASS":
        raise RobustnessEvaluationError("event payload must have status PASS")
    if event_payload.get("research_only") is not True or event_payload.get("final_holdout_eligible") is not False:
        raise RobustnessEvaluationError("event payload must be research-only and not final-holdout eligible")
    if event_payload.get("schema") != "VELTRIX_XAUUSD_MULTI_POSITION_EVENTS_V1":
        raise RobustnessEvaluationError("unsupported event payload schema")
    source_hash = event_payload.get("source_sha256")
    policy_hash = event_payload.get("policy_sha256")
    for value, label in ((source_hash, "source_sha256"), (policy_hash, "policy_sha256")):
        if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
            raise RobustnessEvaluationError(f"{label} must be a SHA-256 hex digest")
    if event_payload.get("data_role") not in ("DEVELOPMENT_ONLY", "PROSPECTIVE_VALIDATION_ONLY"):
        raise RobustnessEvaluationError("final holdout and unclassified data roles are not accepted")
    if not isinstance(broker_snapshot, dict) or broker_snapshot.get("account_mode") != "DEMO" or broker_snapshot.get("trading_enabled") is not False:
        raise RobustnessEvaluationError("broker snapshot must prove DEMO and trading-disabled")
    spec = broker_snapshot.get("instrument_specs", {}).get("XAUUSD")
    if not isinstance(spec, dict):
        raise RobustnessEvaluationError("broker snapshot must contain XAUUSD instrument economics")
    if not isinstance(risk_config, dict) or risk_config.get("original_deposit_verified") is not True:
        raise RobustnessEvaluationError("owner-verified original-deposit risk configuration is required")
    if not slippage_grid or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in slippage_grid):
        raise RobustnessEvaluationError("slippage grid must contain nonnegative integer point assumptions")
    if len(set(slippage_grid)) != len(slippage_grid):
        raise RobustnessEvaluationError("slippage grid must not contain duplicates")

    events = event_payload.get("events")
    if not isinstance(events, list) or not events:
        raise RobustnessEvaluationError("at least one adapted event is required")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            raise RobustnessEvaluationError("every adapted event must be an object")
        candidate = event.get("candidate_id")
        config = event.get("portfolio_config_id")
        if not isinstance(candidate, str) or not candidate.strip():
            raise RobustnessEvaluationError("every event must identify a candidate")
        if not isinstance(config, str) or not config.strip():
            raise RobustnessEvaluationError("every event must identify a portfolio configuration")
        if event.get("execution_authorized") is not False:
            raise RobustnessEvaluationError("adapted events must explicitly prohibit execution")
        groups[(candidate, config)].append(event)

    rows: list[dict[str, Any]] = []
    for (candidate, config), group_events in sorted(groups.items()):
        for slippage in slippage_grid:
            try:
                result = simulate_portfolio(
                    ticks, group_events, spec, risk_config,
                    slippage_points_per_side=slippage,
                )
            except PortfolioSimulationError as exc:
                raise RobustnessEvaluationError(
                    f"{candidate}/{config} failed at {slippage}-point slippage: {exc}"
                ) from exc
            known_gross = [trade["gross_pnl_money"] for trade in result["trades"]
                           if trade.get("gross_pnl_money") is not None]
            unresolved = sum(1 for trade in result["trades"]
                             if trade.get("volume", 0) > 0 and trade.get("gross_pnl_money") is None)
            rows.append({
                "candidate_id": candidate,
                "portfolio_config_id": config,
                "slippage_points_per_side": slippage,
                "event_count": result["summary"]["event_count"],
                "accepted_positions": result["summary"]["accepted_positions"],
                "rejected_events": result["summary"]["rejected_events"],
                "max_concurrent_positions": result["summary"]["max_concurrent_positions"],
                "max_open_stop_risk_money": result["summary"]["max_open_stop_risk_money"],
                "max_open_margin_money": result["summary"]["max_open_margin_money"],
                "unresolved_positions_at_end": result["summary"]["unresolved_positions_at_end"],
                "gross_pnl_money_observed": round(sum(known_gross), 8),
                "gross_pnl_complete": unresolved == 0,
                "net_pnl_money": None,
                "commission_status": "UNVERIFIED_REQUIRED_INPUT",
                "daily_loss_locked": result["summary"]["daily_loss_locked"],
                "daily_loss_lock_time_msc": result["summary"]["daily_loss_lock_time_msc"],
                "max_daily_drawdown_percent_observed": result["summary"]["max_daily_drawdown_percent_observed"],
                "overall_loss_locked": result["summary"]["overall_loss_locked"],
                "overall_loss_lock_time_msc": result["summary"]["overall_loss_lock_time_msc"],
                "max_overall_drawdown_percent_observed": result["summary"]["max_overall_drawdown_percent_observed"],
                "execution_sent": False,
                "actual_fill_claimed": False,
            })

    return {
        "status": "PASS",
        "schema": "VELTRIX_XAUUSD_MULTI_POSITION_ROBUSTNESS_V1",
        "research_only": True,
        "execution_enabled": False,
        "source_sha256": source_hash,
        "policy_sha256": policy_hash,
        "data_role": event_payload["data_role"],
        "candidate_configuration_count": len(groups),
        "slippage_grid_points_per_side": list(slippage_grid),
        "scenario_count": len(rows),
        "commission_status": "UNVERIFIED_REQUIRED_INPUT",
        "net_performance_allowed": False,
        "no_trade_benchmark_gross_pnl_money": 0.0,
        "scenarios": rows,
        "limitations": [
            "Each candidate/configuration is simulated independently against the same quote stream.",
            "Gross outcomes are theoretical quote replay, not broker fills or realized execution.",
            "Unresolved positions make gross PnL incomplete; net PnL is always null until commission is verified.",
            "This report is not final-holdout eligible and cannot select or certify a strategy.",
            "Tick sampling cannot reconstruct intratick price paths or guarantee stop fills.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--broker-snapshot", type=Path, required=True)
    parser.add_argument("--risk-config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        raw_ticks = json.loads(args.ticks.read_text(encoding="utf-8"))
        events = json.loads(args.events.read_text(encoding="utf-8"))
        broker = json.loads(args.broker_snapshot.read_text(encoding="utf-8"))
        risk = json.loads(args.risk_config.read_text(encoding="utf-8"))
        ticks = [PortfolioTick(**item) for item in raw_ticks]
        result = run_robustness_sweep(ticks, events, broker, risk)
    except (OSError, json.JSONDecodeError, TypeError, KeyError, RobustnessEvaluationError) as exc:
        parser.exit(2, f"ROBUSTNESS SWEEP FAIL: {exc}\\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
