import copy
import hashlib
import pytest

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
            "verified_at_utc": "2026-11-13T00:00:00Z",
        },
    }


def source_artifact(tmp_path, evidence):
    path = tmp_path / "exness-account-schedule.txt"
    path.write_bytes(b"synthetic test fixture; not actual broker evidence")
    evidence["evidence"]["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def verify(evidence, source_path):
    return validate_commission_evidence(
        evidence, broker_symbol="XAUUSDm", account_mode="DEMO",
        evaluation_time_utc="2026-11-13T12:00:00Z", source_artifact_path=source_path,
    )


def test_verified_evidence_and_round_turn_cost(tmp_path):
    evidence = valid_evidence()
    verified = verify(evidence, source_artifact(tmp_path, evidence))
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
    source_path = source_artifact(tmp_path, evidence)
    mutation(evidence)
    with pytest.raises(CommissionEvidenceError):
        verify(evidence, source_path)


def test_wrong_requested_account_or_symbol_fails(tmp_path):
    evidence = valid_evidence()
    source_path = source_artifact(tmp_path, evidence)
    with pytest.raises(CommissionEvidenceError):
        validate_commission_evidence(evidence, broker_symbol="XAUUSD", account_mode="DEMO",
                                     evaluation_time_utc="2026-11-13T12:00:00Z", source_artifact_path=source_path)
    with pytest.raises(CommissionEvidenceError):
        validate_commission_evidence(evidence, broker_symbol="XAUUSDm", account_mode="LIVE",
                                     evaluation_time_utc="2026-11-13T12:00:00Z", source_artifact_path=source_path)


def test_invalid_price_and_lot_size_fail(tmp_path):
    evidence = valid_evidence()
    verified = verify(evidence, source_artifact(tmp_path, evidence))
    with pytest.raises(CommissionEvidenceError):
        commission_cost_bps(verified, entry_price_usd_per_oz=0)
    with pytest.raises(CommissionEvidenceError):
        commission_cost_bps(verified, entry_price_usd_per_oz=2000, lot_size=0)


def test_source_hash_must_match_original_artifact(tmp_path):
    evidence = valid_evidence()
    path = source_artifact(tmp_path, evidence)
    path.write_bytes(b"changed source bytes")
    with pytest.raises(CommissionEvidenceError, match="SHA-256"):
        verify(evidence, path)


def test_verification_cannot_precede_effective_date_or_follow_evaluation(tmp_path):
    evidence = valid_evidence()
    path = source_artifact(tmp_path, evidence)
    evidence["evidence"]["verified_at_utc"] = "2025-12-31T23:59:59Z"
    with pytest.raises(CommissionEvidenceError, match="verification timestamp"):
        verify(evidence, path)
    evidence["evidence"]["verified_at_utc"] = "2026-11-13T12:00:01Z"
    with pytest.raises(CommissionEvidenceError, match="verification timestamp"):
        verify(evidence, path)
