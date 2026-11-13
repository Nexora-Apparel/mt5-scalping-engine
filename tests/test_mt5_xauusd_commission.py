import copy
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


def verify(evidence):
    return validate_commission_evidence(
        evidence, broker_symbol="XAUUSDm", account_mode="DEMO",
        evaluation_time_utc="2026-11-13T12:00:00Z",
    )


def test_verified_evidence_and_round_turn_cost():
    verified = verify(valid_evidence())
    assert commission_cost_bps(verified, entry_price_usd_per_oz=2000.0) == pytest.approx(0.035)
    assert net_return_bps(1.0, verified, entry_price_usd_per_oz=2000.0) == pytest.approx(0.965)


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
def test_invalid_evidence_fails_closed(mutation):
    evidence = copy.deepcopy(valid_evidence())
    mutation(evidence)
    with pytest.raises(CommissionEvidenceError):
        verify(evidence)


def test_wrong_requested_account_or_symbol_fails():
    evidence = valid_evidence()
    with pytest.raises(CommissionEvidenceError):
        validate_commission_evidence(evidence, broker_symbol="XAUUSD", account_mode="DEMO",
                                     evaluation_time_utc="2026-11-13T12:00:00Z")
    with pytest.raises(CommissionEvidenceError):
        validate_commission_evidence(evidence, broker_symbol="XAUUSDm", account_mode="LIVE",
                                     evaluation_time_utc="2026-11-13T12:00:00Z")


def test_invalid_price_and_lot_size_fail():
    verified = verify(valid_evidence())
    with pytest.raises(CommissionEvidenceError):
        commission_cost_bps(verified, entry_price_usd_per_oz=0)
    with pytest.raises(CommissionEvidenceError):
        commission_cost_bps(verified, entry_price_usd_per_oz=2000, lot_size=0)
