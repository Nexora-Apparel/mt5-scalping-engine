"""Fail-closed validation and cost conversion for XAUUSD DEMO commission evidence."""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CommissionEvidenceError(ValueError):
    """Raised when broker commission evidence is incomplete or inapplicable."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CommissionEvidenceError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommissionEvidenceError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CommissionEvidenceError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_commission_evidence(
    evidence: dict[str, Any],
    *,
    broker_symbol: str,
    account_mode: str,
    evaluation_time_utc: str,
) -> dict[str, Any]:
    """Validate provenance, applicability, and effective period; never trust a status flag alone."""
    if not isinstance(evidence, dict) or evidence.get("schema") != "VELTRIX_XAUUSD_COMMISSION_EVIDENCE_V1":
        raise CommissionEvidenceError("unsupported commission evidence schema")
    if evidence.get("status") != "VERIFIED":
        raise CommissionEvidenceError("commission evidence status is not VERIFIED")
    instrument = evidence.get("instrument")
    charge = evidence.get("commission")
    source = evidence.get("evidence")
    if not all(isinstance(x, dict) for x in (instrument, charge, source)):
        raise CommissionEvidenceError("instrument, commission, and evidence objects are required")
    if instrument.get("canonical_symbol") != "XAUUSD" or instrument.get("broker_symbol") != broker_symbol:
        raise CommissionEvidenceError("commission evidence symbol does not match the evaluated instrument")
    if instrument.get("account_mode") != account_mode or account_mode != "DEMO":
        raise CommissionEvidenceError("commission evidence must apply to the Exness DEMO account")
    if instrument.get("currency_profit") != "USD":
        raise CommissionEvidenceError("XAUUSD profit currency must be USD")
    contract = instrument.get("contract_size_oz_per_lot")
    if isinstance(contract, bool) or not isinstance(contract, (int, float)) or not math.isfinite(contract) or contract <= 0:
        raise CommissionEvidenceError("verified contract size in ounces per lot is required")
    amount = charge.get("amount_per_lot_per_side")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
        raise CommissionEvidenceError("commission must be a nonnegative finite USD amount per lot per side")
    if charge.get("currency") != "USD" or charge.get("charging_basis") != "PER_SIDE":
        raise CommissionEvidenceError("commission must be explicitly denominated in USD per side")
    effective_from = _utc(charge.get("effective_from_utc"), "effective_from_utc")
    effective_to_raw = charge.get("effective_to_utc")
    effective_to = _utc(effective_to_raw, "effective_to_utc") if effective_to_raw else None
    evaluation = _utc(evaluation_time_utc, "evaluation_time_utc")
    if effective_to and effective_to <= effective_from:
        raise CommissionEvidenceError("commission effective period is invalid")
    if evaluation < effective_from or (effective_to and evaluation >= effective_to):
        raise CommissionEvidenceError("commission schedule is not effective at evaluation time")
    if source.get("independently_verified") is not True:
        raise CommissionEvidenceError("independent source verification is required")
    if not isinstance(source.get("source_type"), str) or not source["source_type"].strip():
        raise CommissionEvidenceError("source_type is required")
    if not isinstance(source.get("source_reference"), str) or not source["source_reference"].strip():
        raise CommissionEvidenceError("source_reference is required")
    digest = source.get("source_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise CommissionEvidenceError("source_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(source.get("verification_reference"), str) or not source["verification_reference"].strip():
        raise CommissionEvidenceError("independent verification reference is required")
    _utc(source.get("verified_at_utc"), "verified_at_utc")
    return {
        "status": "VERIFIED",
        "broker_symbol": broker_symbol,
        "account_mode": account_mode,
        "contract_size_oz_per_lot": float(contract),
        "commission_usd_per_lot_per_side": float(amount),
        "source_sha256": digest,
        "source_reference": source["source_reference"],
        "verification_reference": source["verification_reference"],
        "effective_from_utc": effective_from.isoformat(),
        "effective_to_utc": effective_to.isoformat() if effective_to else None,
    }


def commission_cost_bps(
    verified: dict[str, Any],
    *,
    entry_price_usd_per_oz: float,
    lot_size: float = 1.0,
) -> float:
    """Round-turn commission in bps of notional; spread is not included or altered here."""
    price = entry_price_usd_per_oz
    lots = lot_size
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
        raise CommissionEvidenceError("entry price must be finite and positive")
    if isinstance(lots, bool) or not isinstance(lots, (int, float)) or not math.isfinite(lots) or lots <= 0:
        raise CommissionEvidenceError("lot size must be finite and positive")
    contract = float(verified["contract_size_oz_per_lot"])
    per_side = float(verified["commission_usd_per_lot_per_side"])
    notional = float(price) * contract * float(lots)
    round_turn = 2.0 * per_side * float(lots)
    return round(round_turn / notional * 10000.0, 10)


def net_return_bps(
    return_before_commission_bps: float,
    verified: dict[str, Any],
    *,
    entry_price_usd_per_oz: float,
    lot_size: float = 1.0,
) -> float:
    gross_after_slippage = return_before_commission_bps
    if isinstance(gross_after_slippage, bool) or not isinstance(gross_after_slippage, (int, float)) or not math.isfinite(gross_after_slippage):
        raise CommissionEvidenceError("pre-commission return must be finite")
    return round(float(gross_after_slippage) - commission_cost_bps(
        verified, entry_price_usd_per_oz=entry_price_usd_per_oz, lot_size=lot_size
    ), 8)
