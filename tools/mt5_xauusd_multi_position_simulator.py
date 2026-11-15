"""Offline, read-only multi-position XAUUSD scalping portfolio simulator.

This module consumes preregistered event proposals and verified bid/ask ticks.
It models overlapping positions, dynamic risk sizing, aggregate stop risk,
broker volume steps, margin reserve, protective exits and a 10-60 second
maximum holding window. It never creates or submits broker orders.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PortfolioSimulationError(ValueError):
    """Raised when portfolio simulation inputs are incomplete or invalid."""


@dataclass(frozen=True)
class PortfolioTick:
    time_msc: int
    bid: float
    ask: float


def _finite_positive(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise PortfolioSimulationError(f"{name} must be finite and positive")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PortfolioSimulationError(f"{name} must be finite and positive") from exc
    if not math.isfinite(number) or number <= 0:
        raise PortfolioSimulationError(f"{name} must be finite and positive")
    return number


def validate_portfolio_ticks(ticks: list[PortfolioTick]) -> None:
    if not isinstance(ticks, list) or not ticks:
        raise PortfolioSimulationError("tick stream must be non-empty")
    previous = 0
    utc_session_day: int | None = None
    for index, tick in enumerate(ticks):
        if not isinstance(tick, PortfolioTick):
            raise PortfolioSimulationError(f"tick {index} must be PortfolioTick")
        if isinstance(tick.time_msc, bool) or not isinstance(tick.time_msc, int) or tick.time_msc <= 0:
            raise PortfolioSimulationError(f"tick {index} timestamp is invalid")
        if tick.time_msc < previous:
            raise PortfolioSimulationError("tick timestamps must be nondecreasing")
        day = tick.time_msc // 86_400_000
        if utc_session_day is None:
            utc_session_day = day
        elif day != utc_session_day:
            raise PortfolioSimulationError(
                "one simulator run must contain exactly one UTC trading date; split sessions before replay"
            )
        if (isinstance(tick.bid, bool) or isinstance(tick.ask, bool) or
            not isinstance(tick.bid, (int, float)) or not isinstance(tick.ask, (int, float)) or
            not math.isfinite(tick.bid) or not math.isfinite(tick.ask)):
            raise PortfolioSimulationError(f"tick {index} quote must contain finite numeric bid/ask values")
        if tick.bid <= 0 or tick.ask < tick.bid:
            raise PortfolioSimulationError(f"tick {index} bid/ask is invalid")
        previous = tick.time_msc


def validate_broker_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate the account and XAUUSD identity envelope before CLI replay."""
    if not isinstance(snapshot, dict) or snapshot.get("account_mode") != "DEMO" or snapshot.get("trading_enabled") is not False:
        raise PortfolioSimulationError("broker snapshot must explicitly prove DEMO mode and trading-disabled")
    identity = snapshot.get("account_identity")
    if not isinstance(identity, dict):
        raise PortfolioSimulationError("broker snapshot must include Exness DEMO account_identity")
    company, server, login_hash = identity.get("company"), identity.get("server"), identity.get("login_sha256")
    if (identity.get("broker") != "Exness" or identity.get("account_mode") != "DEMO" or
        not isinstance(company, str) or "exness" not in company.casefold() or
        not isinstance(server, str) or "exness" not in server.casefold() or
        identity.get("account_currency") != "USD" or
        not isinstance(login_hash, str) or len(login_hash) != 64 or
        any(ch not in "0123456789abcdef" for ch in login_hash.lower())):
        raise PortfolioSimulationError("account_identity must prove Exness company/server, DEMO mode, USD currency, and SHA-256 login fingerprint")
    specs = snapshot.get("instrument_specs")
    if not isinstance(specs, dict) or not isinstance(specs.get("XAUUSD"), dict):
        raise PortfolioSimulationError("broker snapshot must contain XAUUSD instrument economics")
    spec = specs["XAUUSD"]
    if (str(spec.get("currency_base", "")).upper() != "XAU" or
        str(spec.get("currency_profit", "")).upper() != "USD"):
        raise PortfolioSimulationError("XAUUSD contract must explicitly prove XAU base and USD profit currencies")
    _finite_positive(spec.get("contract_size"), "contract_size")
    return spec


def _validate_spec(spec: dict[str, Any]) -> dict[str, float]:
    if not isinstance(spec, dict):
        raise PortfolioSimulationError("broker specification must be an object")
    required = (
        "point_size", "tick_size", "tick_value_loss", "tick_value_profit", "volume_min",
        "volume_max", "volume_step", "margin_per_lot",
    )
    values = {key: _finite_positive(spec.get(key), key) for key in required}
    if values["volume_max"] < values["volume_min"]:
        raise PortfolioSimulationError("volume_max is below volume_min")
    return values


def _validate_events(events: list[dict[str, Any]]) -> None:
    if not isinstance(events, list):
        raise PortfolioSimulationError("events must be a list")
    # Each replay represents one preregistered portfolio configuration.
    # Mixing stop/target/horizon configurations would let mutually exclusive
    # research hypotheses consume one another's risk budget and corrupt the
    # comparison. Run each config independently against the same tick stream.
    config_values = [event.get("portfolio_config_id") for event in events
                     if isinstance(event, dict) and "portfolio_config_id" in event]
    candidate_values = [event.get("candidate_id") for event in events
                        if isinstance(event, dict) and "candidate_id" in event]
    if config_values:
        if len(config_values) != len(events) or any(
            not isinstance(value, str) or not value.strip() for value in config_values
        ):
            raise PortfolioSimulationError(
                "portfolio_config_id must be present and non-empty on every event when used"
            )
        if len(set(config_values)) != 1:
            raise PortfolioSimulationError(
                "events from multiple portfolio configurations must be simulated separately"
            )
    if candidate_values:
        if len(candidate_values) != len(events) or any(
            not isinstance(value, str) or not value.strip() for value in candidate_values
        ):
            raise PortfolioSimulationError(
                "candidate_id must be present and non-empty on every event when used"
            )
        if len(set(candidate_values)) != 1:
            raise PortfolioSimulationError(
                "events from multiple candidate strategies must be simulated separately"
            )
    seen: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise PortfolioSimulationError(f"event {index} must be an object")
        signal_id = event.get("signal_id")
        if not isinstance(signal_id, str) or not signal_id.strip() or signal_id in seen:
            raise PortfolioSimulationError("signal_id values must be unique non-empty strings")
        seen.add(signal_id)
        stamp = event.get("signal_window_end_msc")
        if isinstance(stamp, bool) or not isinstance(stamp, int) or stamp <= 0:
            raise PortfolioSimulationError(f"{signal_id}: invalid signal_window_end_msc")
        if event.get("direction") not in ("long", "short"):
            raise PortfolioSimulationError(f"{signal_id}: direction must be long or short")
        hold = event.get("hold_seconds")
        if isinstance(hold, bool) or not isinstance(hold, int) or not 10 <= hold <= 60:
            raise PortfolioSimulationError(f"{signal_id}: hold_seconds must be 10-60")
        _finite_positive(event.get("stop_distance_price"), f"{signal_id}.stop_distance_price")
        _finite_positive(event.get("take_profit_distance_price"), f"{signal_id}.take_profit_distance_price")


def _floor_volume(raw: float, minimum: float, maximum: float, step: float) -> float:
    raw = min(raw, maximum)
    steps = math.floor(raw / step + 1e-10)
    volume = round(steps * step, max(0, min(10, int(math.ceil(-math.log10(step))) + 2)))
    return volume if volume >= minimum - 1e-10 else 0.0


def _resolve_exit(
    ticks: list[PortfolioTick],
    stamps: list[int],
    entry_index: int,
    direction: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
    hold_seconds: int,
    *,
    max_tick_gap_ms: int,
    exit_tolerance_ms: int,
) -> tuple[str, int | None, float | None]:
    entry_time = ticks[entry_index].time_msc
    previous_time = entry_time
    deadline = entry_time + hold_seconds * 1000
    for index in range(entry_index + 1, len(ticks)):
        tick = ticks[index]
        if tick.time_msc - previous_time > max_tick_gap_ms:
            return "DATA_GAP_UNRESOLVED", None, None
        previous_time = tick.time_msc
        executable_exit = tick.bid if direction == "long" else tick.ask
        if direction == "long":
            if executable_exit <= stop_price:
                return "STOP_LOSS", tick.time_msc, executable_exit
            if executable_exit >= target_price:
                return "TAKE_PROFIT", tick.time_msc, executable_exit
        else:
            if executable_exit >= stop_price:
                return "STOP_LOSS", tick.time_msc, executable_exit
            if executable_exit <= target_price:
                return "TAKE_PROFIT", tick.time_msc, executable_exit
        if tick.time_msc >= deadline:
            if tick.time_msc - deadline > exit_tolerance_ms:
                return "EXIT_QUOTE_TIMEOUT", None, None
            return "TIME_STOP", tick.time_msc, executable_exit
    return "END_OF_DATA_UNRESOLVED", None, None


def simulate_portfolio(
    ticks: list[PortfolioTick],
    events: list[dict[str, Any]],
    broker_spec: dict[str, Any],
    risk_config: dict[str, Any],
    *,
    slippage_points_per_side: int = 0,
    entry_max_wait_ms: int = 5000,
    exit_tolerance_ms: int = 2000,
    max_tick_gap_ms: int = 5000,
) -> dict[str, Any]:
    """Simulate overlapping positions with risk- and margin-limited sizing."""
    validate_portfolio_ticks(ticks)
    _validate_events(events)
    spec = _validate_spec(broker_spec)
    if not isinstance(risk_config, dict):
        raise PortfolioSimulationError("risk_config must be an object")
    equity = _finite_positive(risk_config.get("equity"), "equity")
    original_deposit = _finite_positive(risk_config.get("original_deposit"), "original_deposit")
    if risk_config.get("original_deposit_verified") is not True:
        raise PortfolioSimulationError("original_deposit must be explicitly owner-verified")
    overall_loss_raw = risk_config.get("max_overall_account_loss_percent", 50.0)
    if isinstance(overall_loss_raw, bool) or not isinstance(overall_loss_raw, (int, float)):
        raise PortfolioSimulationError("max_overall_account_loss_percent must be numeric")
    overall_loss_pct = float(overall_loss_raw)
    if not math.isfinite(overall_loss_pct) or overall_loss_pct <= 0 or overall_loss_pct > 50.0:
        raise PortfolioSimulationError("max_overall_account_loss_percent must be positive and no greater than the 50.00% policy ceiling")
    risk_pct = _finite_positive(risk_config.get("risk_per_trade_percent"), "risk_per_trade_percent")
    portfolio_pct = _finite_positive(risk_config.get("max_portfolio_risk_percent"), "max_portfolio_risk_percent")
    free_margin = _finite_positive(risk_config.get("initial_free_margin"), "initial_free_margin")
    margin_reserve_raw = risk_config.get("margin_reserve_money", 0.0)
    if isinstance(margin_reserve_raw, bool) or not isinstance(margin_reserve_raw, (int, float)):
        raise PortfolioSimulationError("margin_reserve_money must be numeric")
    margin_reserve = float(margin_reserve_raw)
    if not math.isfinite(margin_reserve) or margin_reserve < 0:
        raise PortfolioSimulationError("margin_reserve_money must be finite and nonnegative")
    daily_loss_raw = risk_config.get("max_daily_loss_percent", 15.0)
    if isinstance(daily_loss_raw, bool) or not isinstance(daily_loss_raw, (int, float)):
        raise PortfolioSimulationError("max_daily_loss_percent must be numeric")
    daily_loss_pct = float(daily_loss_raw)
    if not math.isfinite(daily_loss_pct) or daily_loss_pct <= 0 or daily_loss_pct > 15.0:
        raise PortfolioSimulationError("max_daily_loss_percent must be positive and no greater than the 15.00% policy ceiling")
    if risk_pct > 0.25 or portfolio_pct > 0.50:
        raise PortfolioSimulationError("risk configuration exceeds existing 0.25%/0.50% hard ceilings")
    if isinstance(slippage_points_per_side, bool) or not isinstance(slippage_points_per_side, int) or slippage_points_per_side < 0:
        raise PortfolioSimulationError("slippage_points_per_side must be a nonnegative integer")
    timing_values = (entry_max_wait_ms, exit_tolerance_ms, max_tick_gap_ms)
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in timing_values):
        raise PortfolioSimulationError("timing tolerances must be positive integers")

    stamps = [tick.time_msc for tick in ticks]
    slip = slippage_points_per_side * spec["point_size"]
    initial_portfolio_limit = equity * portfolio_pct / 100.0
    initial_per_trade_budget = equity * risk_pct / 100.0
    active: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    daily_realized_pnl = 0.0
    daily_loss_locked = False
    overall_loss_locked = ((original_deposit - equity) / original_deposit * 100.0) >= overall_loss_pct
    daily_loss_lock_time_msc: int | None = None
    overall_loss_lock_time_msc: int | None = ticks[0].time_msc if overall_loss_locked else None
    max_daily_drawdown_pct = 0.0
    max_overall_drawdown_pct = max(0.0, (original_deposit - equity) / original_deposit * 100.0)
    max_concurrent = 0
    max_open_risk = 0.0
    max_margin_used = 0.0

    last_processed_tick_index = -1

    def advance_portfolio(to_index: int) -> tuple[float, float]:
        """Advance marked equity and loss latches over every observed quote."""
        nonlocal active, daily_realized_pnl, daily_loss_locked, overall_loss_locked
        nonlocal daily_loss_lock_time_msc, overall_loss_lock_time_msc
        nonlocal max_daily_drawdown_pct, max_overall_drawdown_pct
        for tick_index in range(last_processed_tick_index + 1, to_index + 1):
            tick = ticks[tick_index]
            matured = [position for position in active
                       if position["exit_time_msc"] is not None and position["exit_time_msc"] <= tick.time_msc]
            for position in matured:
                if position["gross_pnl_money"] is not None:
                    daily_realized_pnl += position["gross_pnl_money"]
            active = [position for position in active
                      if position["exit_time_msc"] is None or position["exit_time_msc"] > tick.time_msc]
            unrealized = 0.0
            for position in active:
                mark = tick.bid - slip if position["direction"] == "long" else tick.ask + slip
                signed_delta = ((mark - position["entry_price"]) if position["direction"] == "long"
                                else (position["entry_price"] - mark))
                tick_value = spec["tick_value_profit"] if signed_delta >= 0 else spec["tick_value_loss"]
                unrealized += (signed_delta / spec["tick_size"]) * tick_value * position["volume"]
            marked = equity + daily_realized_pnl + unrealized
            daily_drawdown = max(0.0, (equity - marked) / equity * 100.0)
            overall_drawdown = max(0.0, (original_deposit - marked) / original_deposit * 100.0)
            max_daily_drawdown_pct = max(max_daily_drawdown_pct, daily_drawdown)
            max_overall_drawdown_pct = max(max_overall_drawdown_pct, overall_drawdown)
            if daily_drawdown >= daily_loss_pct and not daily_loss_locked:
                daily_loss_locked = True
                daily_loss_lock_time_msc = tick.time_msc
            if overall_drawdown >= overall_loss_pct and not overall_loss_locked:
                overall_loss_locked = True
                overall_loss_lock_time_msc = tick.time_msc

        # Recompute at the requested quote even when multiple signals share it.
        tick = ticks[to_index]
        unrealized = 0.0
        for position in active:
            mark = tick.bid - slip if position["direction"] == "long" else tick.ask + slip
            signed_delta = ((mark - position["entry_price"]) if position["direction"] == "long"
                            else (position["entry_price"] - mark))
            tick_value = spec["tick_value_profit"] if signed_delta >= 0 else spec["tick_value_loss"]
            unrealized += (signed_delta / spec["tick_size"]) * tick_value * position["volume"]
        return equity + daily_realized_pnl + unrealized, unrealized

    ordered = sorted(events, key=lambda item: (item["signal_window_end_msc"], item["signal_id"]))
    for event in ordered:
        signal_end = event["signal_window_end_msc"]
        entry_index = bisect.bisect_right(stamps, signal_end)
        if entry_index >= len(ticks) or ticks[entry_index].time_msc - signal_end > entry_max_wait_ms:
            trades.append({"signal_id": event["signal_id"], "status": "ENTRY_QUOTE_TIMEOUT", "execution_sent": False})
            continue
        entry_tick = ticks[entry_index]
        entry_time = entry_tick.time_msc
        marked_equity, unrealized_pnl = advance_portfolio(entry_index)
        last_processed_tick_index = entry_index
        daily_drawdown_pct = max(0.0, (equity - marked_equity) / equity * 100.0)
        overall_drawdown_pct = max(0.0, (original_deposit - marked_equity) / original_deposit * 100.0)
        if overall_loss_locked:
            trades.append({
                "signal_id": event["signal_id"], "status": "REJECTED_OVERALL_LOSS_LOCK",
                "overall_drawdown_percent": round(overall_drawdown_pct, 8),
                "overall_loss_limit_percent": overall_loss_pct, "execution_sent": False,
            })
            continue
        if daily_drawdown_pct >= daily_loss_pct:
            daily_loss_locked = True
        if daily_loss_locked:
            trades.append({
                "signal_id": event["signal_id"], "status": "REJECTED_DAILY_LOSS_LOCK",
                "daily_drawdown_percent": round(daily_drawdown_pct, 8),
                "daily_loss_limit_percent": daily_loss_pct, "execution_sent": False,
            })
            continue
        current_open_risk = sum(position["risk_money"] for position in active)
        margin_used = sum(position["margin_money"] for position in active)
        max_open_risk = max(max_open_risk, current_open_risk)
        max_margin_used = max(max_margin_used, margin_used)

        stop_distance = float(event["stop_distance_price"])
        target_distance = float(event["take_profit_distance_price"])
        loss_per_lot = (stop_distance / spec["tick_size"]) * spec["tick_value_loss"]
        if not math.isfinite(loss_per_lot) or loss_per_lot <= 0:
            raise PortfolioSimulationError(f"{event['signal_id']}: invalid loss_per_lot")
        # Recalculate risk budgets from marked equity at each decision point.
        # This preserves automatic sizing after realized and floating PnL changes.
        portfolio_limit = max(0.0, marked_equity) * portfolio_pct / 100.0
        per_trade_budget = max(0.0, marked_equity) * risk_pct / 100.0
        remaining_portfolio_risk = portfolio_limit - current_open_risk
        allowed_loss = min(per_trade_budget, remaining_portfolio_risk)
        if allowed_loss <= 0:
            trades.append({
                "signal_id": event["signal_id"], "status": "REJECTED_AGGREGATE_RISK",
                "current_open_risk_money": round(current_open_risk, 8),
                "remaining_risk_capacity_money": round(max(0.0, remaining_portfolio_risk), 8),
                "execution_sent": False,
            })
            continue

        volume = _floor_volume(allowed_loss / loss_per_lot, spec["volume_min"], spec["volume_max"], spec["volume_step"])
        if volume <= 0:
            trades.append({
                "signal_id": event["signal_id"], "status": "REJECTED_BELOW_MIN_VOLUME",
                "allowed_loss_money": round(allowed_loss, 8), "execution_sent": False,
            })
            continue
        risk_money = volume * loss_per_lot
        margin_money = volume * spec["margin_per_lot"]
        if risk_money > allowed_loss + 1e-8:
            trades.append({"signal_id": event["signal_id"], "status": "REJECTED_ROUNDING_RISK", "execution_sent": False})
            continue
        available_free_margin = free_margin + daily_realized_pnl + unrealized_pnl - margin_used
        if available_free_margin - margin_money < margin_reserve:
            trades.append({
                "signal_id": event["signal_id"], "status": "REJECTED_MARGIN_RESERVE",
                "margin_required_money": round(margin_money, 8),
                "free_margin_before_entry": round(available_free_margin, 8),
                "execution_sent": False,
            })
            continue

        direction = event["direction"]
        raw_entry = entry_tick.ask if direction == "long" else entry_tick.bid
        entry_price = raw_entry + slip if direction == "long" else raw_entry - slip
        if direction == "long":
            stop_price, target_price = entry_price - stop_distance, entry_price + target_distance
        else:
            stop_price, target_price = entry_price + stop_distance, entry_price - target_distance
        exit_reason, exit_time, raw_exit = _resolve_exit(
            ticks, stamps, entry_index, direction, entry_price, stop_price, target_price,
            event["hold_seconds"], max_tick_gap_ms=max_tick_gap_ms,
            exit_tolerance_ms=exit_tolerance_ms,
        )
        if raw_exit is None:
            exit_price = None
            pnl = None
        else:
            exit_price = raw_exit - slip if direction == "long" else raw_exit + slip
            signed_delta = (exit_price - entry_price) if direction == "long" else (entry_price - exit_price)
            tick_value = spec["tick_value_profit"] if signed_delta >= 0 else spec["tick_value_loss"]
            pnl = (signed_delta / spec["tick_size"]) * tick_value * volume

        record = {
            "signal_id": event["signal_id"],
            "candidate_id": event.get("candidate_id"),
            "direction": direction,
            "status": exit_reason,
            "entry_time_msc": entry_time,
            "exit_time_msc": exit_time,
            "holding_seconds": round((exit_time - entry_time) / 1000.0, 6) if exit_time else None,
            "entry_price": entry_price,
            "entry_price_with_slippage": round(entry_price, 9),
            "exit_price_with_slippage": round(exit_price, 9) if exit_price is not None else None,
            "stop_price": round(stop_price, 9),
            "take_profit_price": round(target_price, 9),
            "volume": volume,
            "risk_money": round(risk_money, 8),
            "risk_budget_at_entry_money": round(per_trade_budget, 8),
            "portfolio_limit_at_entry_money": round(portfolio_limit, 8),
            "equity_at_entry": round(marked_equity, 8),
            "margin_money": round(margin_money, 8),
            "gross_pnl_money": round(pnl, 8) if pnl is not None else None,
            "commission_status": "UNVERIFIED_REQUIRED_INPUT",
            "net_pnl_money": None,
            "execution_sent": False,
            "actual_fill_claimed": False,
        }
        trades.append(record)
        position = {
            "signal_id": event["signal_id"],
            "risk_money": risk_money,
            "margin_money": margin_money,
            "exit_time_msc": exit_time,
            "direction": direction,
            "entry_price": entry_price,
            "volume": volume,
            "gross_pnl_money": pnl,
        }
        # Unknown exits remain in the active exposure set for the rest of the dataset.
        active.append(position)
        max_concurrent = max(max_concurrent, len(active))
        max_open_risk = max(max_open_risk, sum(item["risk_money"] for item in active))
        max_margin_used = max(max_margin_used, sum(item["margin_money"] for item in active))

    # Advance through every remaining quote so transient floating breaches latch.
    final_equity, final_unrealized = advance_portfolio(len(ticks) - 1)
    last_processed_tick_index = len(ticks) - 1
    final_daily_drawdown_pct = max(0.0, (equity - final_equity) / equity * 100.0)
    final_overall_drawdown_pct = max(0.0, (original_deposit - final_equity) / original_deposit * 100.0)
    unresolved = [item for item in active if item["exit_time_msc"] is None]
    return {
        "status": "PASS",
        "schema": "VELTRIX_XAUUSD_MULTI_POSITION_PORTFOLIO_SIM_V1",
        "research_only": True,
        "execution_enabled": False,
        "commission_status": "UNVERIFIED_REQUIRED_INPUT",
        "net_performance_allowed": False,
        "slippage_points_per_side": slippage_points_per_side,
        "risk_config": {
            "equity": equity,
            "original_deposit": original_deposit,
            "original_deposit_verified": True,
            "max_overall_account_loss_percent": overall_loss_pct,
            "risk_per_trade_percent": risk_pct,
            "max_portfolio_risk_percent": portfolio_pct,
            "initial_per_trade_budget_money": round(initial_per_trade_budget, 8),
            "initial_portfolio_limit_money": round(initial_portfolio_limit, 8),
            "max_daily_loss_percent": daily_loss_pct,
            "daily_profit_target_money": None,
            "daily_profit_cap_money": None,
            "overall_account_loss_limit_percent": overall_loss_pct,
            "overall_account_loss_enforcement": "IMPLEMENTED_RESEARCH_ONLY",
        },
        "summary": {
            "event_count": len(events),
            "accepted_positions": sum(item.get("volume", 0) > 0 for item in trades),
            "rejected_events": sum(item["status"].startswith("REJECTED") or item["status"] == "ENTRY_QUOTE_TIMEOUT" for item in trades),
            "max_concurrent_positions": max_concurrent,
            "max_open_stop_risk_money": round(max_open_risk, 8),
            "max_open_margin_money": round(max_margin_used, 8),
            "unresolved_positions_at_end": len(unresolved),
            "daily_realized_gross_pnl_money": round(daily_realized_pnl, 8),
            "daily_unrealized_gross_pnl_money": round(final_unrealized, 8),
            "daily_drawdown_percent_at_end": round(final_daily_drawdown_pct, 8),
            "max_daily_drawdown_percent_observed": round(max_daily_drawdown_pct, 8),
            "daily_loss_locked": daily_loss_locked,
            "daily_loss_lock_time_msc": daily_loss_lock_time_msc,
            "overall_drawdown_percent_at_end": round(final_overall_drawdown_pct, 8),
            "max_overall_drawdown_percent_observed": round(max_overall_drawdown_pct, 8),
            "overall_loss_locked": overall_loss_locked,
            "overall_loss_lock_time_msc": overall_loss_lock_time_msc,
        },
        "trades": trades,
        "limitations": [
            "Theoretical bid/ask replay only; no orders or actual fills are created.",
            "Broker margin_per_lot and tick economics must come from the verified account/symbol snapshot.",
            "Commission remains unverified and net PnL is deliberately null.",
            "Overall account-loss lock is measured against the explicitly owner-verified original-deposit input; daily and overall locks are independent.",
            "Risk sizing recalculates from marked equity at every entry decision; this is a research approximation and does not replace broker-side pre-trade validation.",
            "A tick gap beyond the configured freshness bound leaves exposure unresolved and reserves its risk.",
            "SL/TP triggers are evaluated on observed ticks; gaps can conceal intratick price paths.",
            "This simulator is separate from the frozen Phase 8 one-position evaluation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticks", type=Path, required=True, help="JSON array of {time_msc,bid,ask} quote records")
    parser.add_argument("--events", type=Path, required=True, help="JSON object containing an events array")
    parser.add_argument("--broker-spec", type=Path, required=True, help="Verified broker symbol/account cost snapshot")
    parser.add_argument("--risk-config", type=Path, required=True, help="Risk and free-margin assumptions")
    parser.add_argument("--slippage-points-per-side", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        raw_ticks = json.loads(args.ticks.read_text(encoding="utf-8"))
        events_payload = json.loads(args.events.read_text(encoding="utf-8"))
        spec_payload = json.loads(args.broker_spec.read_text(encoding="utf-8"))
        risk_payload = json.loads(args.risk_config.read_text(encoding="utf-8"))
        ticks = [PortfolioTick(**item) for item in raw_ticks]
        spec = validate_broker_snapshot(spec_payload)
        result = simulate_portfolio(
            ticks, events_payload.get("events"), spec, risk_payload,
            slippage_points_per_side=args.slippage_points_per_side,
        )
    except (OSError, json.JSONDecodeError, TypeError, KeyError, PortfolioSimulationError) as exc:
        parser.exit(2, f"PORTFOLIO SIMULATION FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
