"""Fail-closed validation and cost conversion for XAUUSD DEMO commission evidence."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


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
    source_artifact_path: Path,
    verification_artifact_path: Path,
    verification_public_key_path: Path,
    trusted_reviewer_key_sha256: str,
    evaluation_start_utc: str | None = None,
    evaluation_end_utc: str | None = None,
    verification_time_utc: str | None = None,
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
    evaluation_start = _utc(evaluation_start_utc, "evaluation_start_utc") if evaluation_start_utc else evaluation
    evaluation_end = _utc(evaluation_end_utc, "evaluation_end_utc") if evaluation_end_utc else evaluation
    verification_time = _utc(verification_time_utc, "verification_time_utc") if verification_time_utc else datetime.now(timezone.utc)
    if evaluation_start > evaluation_end:
        raise CommissionEvidenceError("evaluation time range is invalid")
    if effective_to and effective_to <= effective_from:
        raise CommissionEvidenceError("commission effective period is invalid")
    if evaluation_start < effective_from or (effective_to and evaluation_end >= effective_to):
        raise CommissionEvidenceError("commission schedule does not cover the full evaluation period")
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
    verified_at = _utc(source.get("verified_at_utc"), "verified_at_utc")
    if verified_at > verification_time:
        raise CommissionEvidenceError("independent verification timestamp cannot be in the future")
    if not isinstance(source_artifact_path, Path) or not source_artifact_path.is_file():
        raise CommissionEvidenceError("the original commission source artifact must be supplied for hash verification")
    digest_calculator = hashlib.sha256()
    try:
        with source_artifact_path.open("rb") as source_file:
            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                digest_calculator.update(chunk)
    except OSError as exc:
        raise CommissionEvidenceError("commission source artifact cannot be read") from exc
    if digest_calculator.hexdigest() != digest:
        raise CommissionEvidenceError("commission source artifact SHA-256 does not match the evidence record")
    verification_digest = source.get("verification_sha256")
    if not isinstance(verification_digest, str) or not _SHA256.fullmatch(verification_digest):
        raise CommissionEvidenceError("verification_sha256 must be a lowercase SHA-256 digest")
    if verification_digest == digest:
        raise CommissionEvidenceError("independent verification must be a separate artifact")
    if not isinstance(verification_artifact_path, Path) or not verification_artifact_path.is_file():
        raise CommissionEvidenceError("the independent verification artifact must be supplied for hash verification")
    verification_calculator = hashlib.sha256()
    try:
        with verification_artifact_path.open("rb") as verification_file:
            for chunk in iter(lambda: verification_file.read(1024 * 1024), b""):
                verification_calculator.update(chunk)
    except OSError as exc:
        raise CommissionEvidenceError("independent verification artifact cannot be read") from exc
    if verification_calculator.hexdigest() != verification_digest:
        raise CommissionEvidenceError("independent verification artifact SHA-256 does not match the evidence record")

    # The review artifact is a signed JSON attestation. Its signature is checked
    # against a separately pinned fingerprint, never a key supplied by the artifact.
    if not isinstance(trusted_reviewer_key_sha256, str) or not _SHA256.fullmatch(trusted_reviewer_key_sha256):
        raise CommissionEvidenceError("trusted reviewer public-key fingerprint must be pinned out of band")
    if not isinstance(verification_public_key_path, Path) or not verification_public_key_path.is_file():
        raise CommissionEvidenceError("trusted reviewer public key file is required")
    try:
        public_key = serialization.load_pem_public_key(verification_public_key_path.read_bytes())
        if not isinstance(public_key, Ed25519PublicKey):
            raise CommissionEvidenceError("reviewer public key must be Ed25519")
        raw_public_key = public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        actual_fingerprint = hashlib.sha256(raw_public_key).hexdigest()
        if actual_fingerprint != trusted_reviewer_key_sha256:
            raise CommissionEvidenceError("reviewer public key does not match the out-of-band trusted fingerprint")
        attestation = json.loads(verification_artifact_path.read_text(encoding="utf-8"))
        if not isinstance(attestation, dict):
            raise CommissionEvidenceError("review attestation must be a JSON object")
        signature_text = attestation.get("signature_ed25519_base64")
        signed_payload = {key: value for key, value in attestation.items() if key != "signature_ed25519_base64"}
        canonical_payload = json.dumps(signed_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        signature = base64.b64decode(signature_text, validate=True)
        public_key.verify(signature, canonical_payload)
    except CommissionEvidenceError:
        raise
    except (OSError, ValueError, TypeError, json.JSONDecodeError, InvalidSignature) as exc:
        raise CommissionEvidenceError("review attestation signature or encoding is invalid") from exc

    for required_text in ("reviewer_identity", "reviewer_organization", "reviewer_role", "reviewed_at_utc", "independence_statement"):
        value = attestation.get(required_text)
        if not isinstance(value, str) or not value.strip():
            raise CommissionEvidenceError(f"review attestation {required_text} is required")

    expected_fields = {
        "schema": "VELTRIX_COMMISSION_REVIEW_ATTESTATION_V1",
        "review_status": "APPROVED",
        "reviewer_identity": attestation.get("reviewer_identity"),
        "reviewer_organization": attestation.get("reviewer_organization"),
        "reviewer_role": attestation.get("reviewer_role"),
        "reviewed_source_sha256": digest,
        "canonical_symbol": "XAUUSD",
        "broker_symbol": broker_symbol,
        "account_mode": account_mode,
        "currency": "USD",
        "contract_size_oz_per_lot": float(contract),
        "commission_usd_per_lot_per_side": float(amount),
        "charging_basis": "PER_SIDE",
        "effective_from_utc": charge.get("effective_from_utc"),
        "effective_to_utc": charge.get("effective_to_utc"),
        "reviewed_at_utc": attestation.get("reviewed_at_utc"),
        "independence_statement": attestation.get("independence_statement"),
    }
    for field, expected_value in expected_fields.items():
        actual_value = attestation.get(field)
        if expected_value is None:
            if actual_value is not None:
                raise CommissionEvidenceError(f"review attestation {field} does not match commission evidence")
        elif field in ("contract_size_oz_per_lot", "commission_usd_per_lot_per_side"):
            if actual_value != expected_value:
                raise CommissionEvidenceError(f"review attestation {field} does not match commission evidence")
        elif not isinstance(actual_value, str) or not actual_value.strip():
            raise CommissionEvidenceError(f"review attestation {field} is required")
        elif actual_value != expected_value:
            raise CommissionEvidenceError(f"review attestation {field} does not match commission evidence")
    if _utc(attestation["reviewed_at_utc"], "reviewed_at_utc") != verified_at:
        raise CommissionEvidenceError("review attestation timestamp does not match evidence verification timestamp")
    if len(attestation["independence_statement"]) < 40:
        raise CommissionEvidenceError("reviewer independence attestation is insufficient")
    return {
        "status": "VERIFIED",
        "broker_symbol": broker_symbol,
        "account_mode": account_mode,
        "contract_size_oz_per_lot": float(contract),
        "commission_usd_per_lot_per_side": float(amount),
        "source_sha256": digest,
        "verification_sha256": verification_digest,
        "source_reference": source["source_reference"],
        "verification_reference": source["verification_reference"],
        "reviewer_identity": attestation["reviewer_identity"],
        "reviewer_organization": attestation["reviewer_organization"],
        "reviewer_role": attestation["reviewer_role"],
        "reviewer_key_sha256": actual_fingerprint,
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
