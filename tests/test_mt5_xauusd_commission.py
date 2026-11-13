import copy
import hashlib
import json
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.mt5_xauusd_commission import (
    CommissionEvidenceError,
    commission_cost_bps,
    net_return_bps,
    validate_commission_evidence,
)


def valid_evidence():
    return {
        "schema": "VELTRIX_XAUUSD_COMMISSION_EVIDENCE_V1",
        "status": "VERIFIED",
        "instrument": {
            "canonical_symbol": "XAUUSD", "broker_symbol": "XAUUSDm",
            "account_mode": "DEMO", "currency_profit": "USD",
            "contract_size_oz_per_lot": 100.0,
        },
        "commission": {
            "currency": "USD", "amount_per_lot_per_side": 3.5,
            "charging_basis": "PER_SIDE",
            "effective_from_utc": "2026-01-01T00:00:00Z", "effective_to_utc": None,
        },
        "evidence": {
            "source_type": "ACCOUNT_SCHEDULE", "source_reference": "secure://sanitized-source",
            "source_sha256": "a" * 64, "independently_verified": True,
            "verification_reference": "review-record-001",
            "verification_sha256": "b" * 64,
            "verified_at_utc": "2026-11-13T00:00:00Z",
        },
    }


def source_artifact(tmp_path, evidence):
    source_path = tmp_path / "exness-account-schedule.txt"
    verification_path = tmp_path / "independent-review-record.txt"
    source_path.write_bytes(b"synthetic test fixture; not actual broker evidence")
    evidence["evidence"]["source_sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_path = tmp_path / "trusted-reviewer-public.pem"
    public_path.write_bytes(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    raw_public = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    fingerprint = hashlib.sha256(raw_public).hexdigest()
    attestation = {
        "schema": "VELTRIX_COMMISSION_REVIEW_ATTESTATION_V1",
        "review_status": "APPROVED",
        "reviewer_identity": "Synthetic Test Reviewer",
        "reviewer_organization": "Synthetic Test Organization",
        "reviewer_role": "Independent Cost Reviewer",
        "reviewed_source_sha256": evidence["evidence"]["source_sha256"],
        "canonical_symbol": "XAUUSD",
        "broker_symbol": "XAUUSDm",
        "account_mode": "DEMO",
        "currency": "USD",
        "contract_size_oz_per_lot": 100.0,
        "commission_usd_per_lot_per_side": 3.5,
        "charging_basis": "PER_SIDE",
        "effective_from_utc": "2026-01-01T00:00:00Z",
        "effective_to_utc": None,
        "reviewed_at_utc": "2026-11-13T00:00:00Z",
        "independence_statement": "Synthetic test fixture only; no actual broker evidence or reviewer identity is asserted.",
    }
    canonical = json.dumps(attestation, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    import base64
    attestation["signature_ed25519_base64"] = base64.b64encode(private_key.sign(canonical)).decode("ascii")
    verification_path.write_text(json.dumps(attestation, sort_keys=True), encoding="utf-8")
    evidence["evidence"]["verification_sha256"] = hashlib.sha256(verification_path.read_bytes()).hexdigest()
    return source_path, verification_path, public_path, fingerprint


def verify(evidence, source_path, verification_path, public_path, fingerprint):
    return validate_commission_evidence(
        evidence, broker_symbol="XAUUSDm", account_mode="DEMO",
        evaluation_time_utc="2026-11-13T12:00:00Z", source_artifact_path=source_path,
        verification_artifact_path=verification_path,
        verification_public_key_path=public_path,
        trusted_reviewer_key_sha256=fingerprint,
        verification_time_utc="2026-11-14T00:00:00Z",
    )


def test_verified_evidence_and_round_turn_cost(tmp_path):
    evidence = valid_evidence()
    source_path, verification_path, public_path, fingerprint = source_artifact(tmp_path, evidence)
    verified = verify(evidence, source_path, verification_path, public_path, fingerprint)
    assert commission_cost_bps(verified, entry_price_usd_per_oz=2000.0) == pytest.approx(0.35)
    assert net_return_bps(1.0, verified, entry_price_usd_per_oz=2000.0) == pytest.approx(0.65)


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(status="UNVERIFIED_REQUIRED_INPUT"),
    lambda x: x["evidence"].update(independently_verified=False),
    lambda x: x["evidence"].update(source_sha256="bad"),
    lambda x: x["evidence"].update(verification_reference=""),
    lambda x: x["instrument"].update(broker_symbol="XAUUSD"),
    lambda x: x["instrument"].update(account_mode="LIVE"),
    lambda x: x["instrument"].update(currency_profit="EUR"),
    lambda x: x["instrument"].update(contract_size_oz_per_lot=None),
    lambda x: x["commission"].update(currency="EUR"),
    lambda x: x["commission"].update(charging_basis="ROUND_TURN"),
    lambda x: x["commission"].update(effective_from_utc="2027-01-01T00:00:00Z"),
])
def test_invalid_evidence_fails_closed(mutation, tmp_path):
    evidence = copy.deepcopy(valid_evidence())
    source_path, verification_path = source_artifact(tmp_path, evidence)
    mutation(evidence)
    with pytest.raises(CommissionEvidenceError):
        verify(evidence, source_path, verification_path)


def test_wrong_requested_account_or_symbol_fails(tmp_path):
    evidence = valid_evidence()
    source_path, verification_path = source_artifact(tmp_path, evidence)
    with pytest.raises(CommissionEvidenceError):
        validate_commission_evidence(evidence, broker_symbol="XAUUSD", account_mode="DEMO",
                                     evaluation_time_utc="2026-11-13T12:00:00Z", source_artifact_path=source_path,
                                     verification_artifact_path=verification_path,
                                     verification_public_key_path=public_path, trusted_reviewer_key_sha256=fingerprint)
    with pytest.raises(CommissionEvidenceError):
        validate_commission_evidence(evidence, broker_symbol="XAUUSDm", account_mode="LIVE",
                                     evaluation_time_utc="2026-11-13T12:00:00Z", source_artifact_path=source_path,
                                     verification_artifact_path=verification_path)


def test_invalid_price_and_lot_size_fail(tmp_path):
    evidence = valid_evidence()
    source_path, verification_path = source_artifact(tmp_path, evidence)
    verified = verify(evidence, source_path, verification_path)
    with pytest.raises(CommissionEvidenceError):
        commission_cost_bps(verified, entry_price_usd_per_oz=0)
    with pytest.raises(CommissionEvidenceError):
        commission_cost_bps(verified, entry_price_usd_per_oz=2000, lot_size=0)


def test_source_hash_must_match_original_artifact(tmp_path):
    evidence = valid_evidence()
    source_path, verification_path = source_artifact(tmp_path, evidence)
    source_path.write_bytes(b"changed source bytes")
    with pytest.raises(CommissionEvidenceError, match="SHA-256"):
        verify(evidence, source_path, verification_path)


def test_historical_evaluation_can_be_verified_after_the_market_period(tmp_path):
    evidence = valid_evidence()
    source_path, verification_path = source_artifact(tmp_path, evidence)
    evidence["evidence"]["verified_at_utc"] = "2026-11-13T12:00:01Z"
    verified = verify(evidence, source_path, verification_path)
    assert verified["status"] == "VERIFIED"
    evidence["evidence"]["verified_at_utc"] = "2026-11-14T00:00:01Z"
    with pytest.raises(CommissionEvidenceError, match="cannot be in the future"):
        verify(evidence, source_path, verification_path)


def test_commission_schedule_must_cover_entire_evaluation_period(tmp_path):
    evidence = valid_evidence()
    source_path, verification_path = source_artifact(tmp_path, evidence)
    evidence["commission"]["effective_to_utc"] = "2026-11-14T00:00:00Z"
    with pytest.raises(CommissionEvidenceError, match="full evaluation period"):
        validate_commission_evidence(
            evidence, broker_symbol="XAUUSDm", account_mode="DEMO",
            evaluation_time_utc="2026-11-13T12:00:00Z",
            evaluation_start_utc="2026-11-12T00:00:00Z",
            evaluation_end_utc="2026-11-15T00:00:00Z",
            verification_time_utc="2026-11-16T00:00:00Z",
            source_artifact_path=source_path,
            verification_artifact_path=verification_path,
            verification_public_key_path=public_path,
            trusted_reviewer_key_sha256=fingerprint,
        )


def test_independent_verification_artifact_must_match_its_own_hash(tmp_path):
    evidence = valid_evidence()
    source_path, verification_path = source_artifact(tmp_path, evidence)
    verification_path.write_bytes(b"altered review artifact")
    with pytest.raises(CommissionEvidenceError, match="verification artifact SHA-256"):
        verify(evidence, source_path, verification_path)


def test_missing_independent_verification_artifact_fails_closed(tmp_path):
    evidence = valid_evidence()
    source_path, verification_path, public_path, fingerprint = source_artifact(tmp_path, evidence)
    with pytest.raises(CommissionEvidenceError, match="independent verification artifact"):
        validate_commission_evidence(
            evidence, broker_symbol="XAUUSDm", account_mode="DEMO",
            evaluation_time_utc="2026-11-13T12:00:00Z",
            source_artifact_path=source_path,
            verification_artifact_path=tmp_path / "missing-review-record.txt",
            verification_public_key_path=public_path,
            trusted_reviewer_key_sha256=fingerprint,
        )
