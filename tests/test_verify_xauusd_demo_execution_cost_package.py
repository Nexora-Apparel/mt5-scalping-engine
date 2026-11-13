import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "verify_xauusd_demo_execution_cost_package.py"
spec = importlib.util.spec_from_file_location("verify_xauusd_demo_execution_cost_package", SOURCE)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def build_package(path, *, deals=0):
    path.mkdir(parents=True, exist_ok=True)
    account = {
        "account_mode": "DEMO", "server": "Exness-MT5Trial", "company": "Exness",
        "currency": "USD", "terminal_connected": True,
        "terminal_trade_allowed": False, "terminal_dlls_allowed": False,
        "login_persisted": False,
    }
    symbol = {
        "canonical_symbol": "XAUUSD", "broker_symbol": "XAUUSDm",
        "currency_base": "XAU", "currency_profit": "USD", "account_currency": "USD",
        "contract_size_oz_per_lot": 100.0, "point": 0.001, "digits": 3,
        "trade_tick_size": 0.001, "trade_tick_value": 0.1,
        "volume_min": 0.01, "volume_max": 200.0, "volume_step": 0.01,
    }
    rows = []
    if deals:
        rows.append({
            "position_ref": "a" * 64, "time_msc": 1800000000000,
            "time_utc": "2027-01-15T08:00:00+00:00", "deal_type": "BUY",
            "deal_entry": "IN", "volume_lots": 0.1, "price": 3000.0,
            "commission_usd": -0.35, "fee_usd": 0.0, "swap_usd": 0.0,
            "profit_usd": 0.0, "symbol": "XAUUSDm",
        })
    with (path / "demo_deals_sanitized.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=verifier.DEAL_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (path / "broker_account_snapshot.json").write_text(json.dumps(account), encoding="utf-8")
    (path / "symbol_spec_snapshot.json").write_text(json.dumps(symbol), encoding="utf-8")
    summary = {
        "schema": "VELTRIX_XAUUSD_DEMO_EXECUTION_COST_OBSERVATIONS_V1",
        "status": "OBSERVATIONS_CAPTURED" if deals else "NEEDS_DEMO_DEAL_HISTORY",
        "broker_symbol": "XAUUSDm", "deal_count_xauusd": len(rows),
        "position_count": 1 if deals else 0,
        "complete_round_trip_position_count": 0,
        "round_trip_observations": ([{
            "position_ref": "a" * 64, "entry_deal_count": 1, "exit_deal_count": 0,
            "opened_volume_lots": 0.1, "closed_volume_lots": 0.0,
            "round_trip_complete_in_export": False,
            "commission_total_usd_signed": -0.35,
            "observed_round_turn_commission_usd_per_lot": None,
            "observed_commission_usd_per_lot_per_side_equivalent": None,
            "commission_observation_status": "INCOMPLETE_OR_AMBIGUOUS_POSITION",
            "fee_total_usd_signed": 0.0, "swap_total_usd_signed": 0.0,
            "profit_total_usd_signed": 0.0,
        }] if deals else []),
        "commission_schedule_status": "UNVERIFIED_REQUIRED_BROKER_SCHEDULE_AND_INDEPENDENT_REVIEW",
        "net_performance_allowed": False,
    }
    (path / "round_trip_cost_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    files = {}
    for name in sorted(verifier.EXPECTED_FILES):
        raw = (path / name).read_bytes()
        files[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    manifest = {
        "schema": "VELTRIX_XAUUSD_DEMO_EXECUTION_COST_PACKAGE_V1",
        "status": summary["status"], "account_mode": "DEMO",
        "broker_symbol": "XAUUSDm",
        "position_reference_scheme": "PER_PACKAGE_SALTED_SHA256",
        "position_reference_salt_sha256": "c" * 64,
        "files": files,
        "commission_schedule_status": "UNVERIFIED_REQUIRED_BROKER_SCHEDULE_AND_INDEPENDENT_REVIEW",
        "net_performance_allowed": False,
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_verifies_empty_history_package_without_unlocking_net_scoring(tmp_path):
    package = build_package(tmp_path / "evidence")
    result = verifier.verify_package(package)
    assert result["status"] == "VERIFIED_PACKAGE"
    assert result["deal_count_xauusd"] == 0
    assert result["commission_schedule_status"].startswith("UNVERIFIED")
    assert result["net_performance_allowed"] is False


def test_verifies_sanitized_deal_observation_package(tmp_path):
    package = build_package(tmp_path / "evidence", deals=1)
    result = verifier.verify_package(package)
    assert result["status"] == "VERIFIED_PACKAGE"
    assert result["deal_count_xauusd"] == 1


def test_rejects_tampered_package_file(tmp_path):
    package = build_package(tmp_path / "evidence")
    (package / "symbol_spec_snapshot.json").write_text("{}", encoding="utf-8")
    with pytest.raises(verifier.PackageVerificationError, match="hash or byte count mismatch"):
        verifier.verify_package(package)


def test_rejects_non_demo_or_trading_enabled_snapshot(tmp_path):
    package = build_package(tmp_path / "evidence")
    account_path = package / "broker_account_snapshot.json"
    account = json.loads(account_path.read_text())
    account["terminal_trade_allowed"] = True
    account_path.write_text(json.dumps(account))
    files = json.loads((package / "manifest.json").read_text())["files"]
    raw = account_path.read_bytes()
    files[account_path.name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    (package / "manifest.json").write_text(json.dumps({
        "schema": "VELTRIX_XAUUSD_DEMO_EXECUTION_COST_PACKAGE_V1",
        "status": "NEEDS_DEMO_DEAL_HISTORY", "account_mode": "DEMO",
        "broker_symbol": "XAUUSDm",
        "position_reference_scheme": "PER_PACKAGE_SALTED_SHA256",
        "position_reference_salt_sha256": "c" * 64,
        "files": files,
        "commission_schedule_status": "UNVERIFIED_REQUIRED_BROKER_SCHEDULE_AND_INDEPENDENT_REVIEW",
        "net_performance_allowed": False,
    }))
    with pytest.raises(verifier.PackageVerificationError, match="read-only controls"):
        verifier.verify_package(package)


def test_verifier_has_no_order_submission_or_management_calls():
    source = SOURCE.read_text()
    for forbidden in ("order_send(", "order_check(", "order_send_async(", "positions_get(", "orders_get("):
        assert forbidden not in source


def test_rejects_deal_timestamp_that_does_not_match_epoch(tmp_path):
    package = build_package(tmp_path / "evidence", deals=1)
    csv_path = package / "demo_deals_sanitized.csv"
    content = csv_path.read_text().replace("2027-01-15T08:00:00+00:00", "2027-01-15T09:00:00+00:00")
    csv_path.write_text(content)
    manifest = json.loads((package / "manifest.json").read_text())
    raw = csv_path.read_bytes()
    manifest["files"][csv_path.name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    (package / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(verifier.PackageVerificationError, match="UTC timestamp"):
        verifier.verify_package(package)


def test_rejects_summary_manifest_status_disagreement(tmp_path):
    package = build_package(tmp_path / "evidence")
    manifest = json.loads((package / "manifest.json").read_text())
    manifest["status"] = "OBSERVATIONS_CAPTURED"
    (package / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(verifier.PackageVerificationError, match="differs from the manifest"):
        verifier.verify_package(package)
