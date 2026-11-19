import csv, hashlib, json
from datetime import datetime, timezone
import pytest
from tools.mt5_tick_market_profile import HEADER, ProfileError, profile_dataset

def row(symbol, stamp):
    return {"schema_version":"1","source_id":"test-source","canonical_symbol":symbol,
            "broker_symbol":symbol+"m","time_msc":str(stamp),
            "time_utc":datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat(),
            "bid":"3000.0","ask":"3000.2","last":"3000.1","volume":"1","volume_real":"1.0","flags":"3"}

def fixture(tmp_path, rows):
    c,m=tmp_path/"ticks.csv",tmp_path/"manifest.json"
    with c.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=HEADER,lineterminator="\n");w.writeheader();w.writerows(rows)
    raw=c.read_bytes()
    m.write_text(json.dumps({"sha256":hashlib.sha256(raw).hexdigest(),"records":len(rows),
        "account_mode":"DEMO","status":"PASS","trading_enabled":False,"dll_imports_enabled":False,
        "instrument_specs":{"XAUUSD":{"point":0.001,"broker_symbol":"XAUUSDm"}}}))
    return c,m

def test_profiles_gold_and_flags_long_gaps(tmp_path):
    base=1_800_000_000_000
    c,m=fixture(tmp_path,[row("XAUUSD",base),row("XAUUSD",base+1000),row("XAUUSD",base+8000)])
    result=profile_dataset(c,m)
    assert result["status"]=="REVIEW" and set(result["symbols"])=={"XAUUSD"}
    assert result["symbols"]["XAUUSD"]["gaps_over_5s"]==1

def test_rejects_silver(tmp_path):
    c,m=fixture(tmp_path,[row("XAGUSD",1_800_000_000_000)])
    with pytest.raises(ProfileError,match="XAUUSD only"): profile_dataset(c,m)

def test_rejects_hash_mismatch(tmp_path):
    c,m=fixture(tmp_path,[row("XAUUSD",1_800_000_000_000)])
    c.write_text(c.read_text()+"\n")
    with pytest.raises(ProfileError,match="SHA-256"): profile_dataset(c,m)

def test_rejects_failed_manifest(tmp_path):
    c,m=fixture(tmp_path,[row("XAUUSD",1_800_000_000_000)])
    d=json.loads(m.read_text());d["status"]="FAIL";m.write_text(json.dumps(d))
    with pytest.raises(ProfileError,match="overall status"): profile_dataset(c,m)

def test_rejects_duplicate_ticks(tmp_path):
    r=row("XAUUSD",1_800_000_000_000);c,m=fixture(tmp_path,[r,r])
    with pytest.raises(ProfileError,match="duplicate"): profile_dataset(c,m)


def legacy_fixture(tmp_path, rows):
    c, m = fixture(tmp_path, rows)
    data = {
        "schema": "VELTRIX_XAUUSD_HISTORICAL_TICK_PROBE_V2",
        "status": "PASS",
        "account_mode": "DEMO",
        "trading_enabled": False,
        "canonical_symbol": "XAUUSD",
        "broker_symbol": "XAUUSDm",
        "instrument_point": 0.001,
        "records": len(rows),
        "sha256": hashlib.sha256(c.read_bytes()).hexdigest(),
    }
    m.write_text(json.dumps(data), encoding="utf-8")
    return c, m


def test_legacy_historical_profile_requires_explicit_opt_in_and_marks_missing_provenance(tmp_path):
    base = 1_800_000_000_000
    c, m = legacy_fixture(tmp_path, [row("XAUUSD", base), row("XAUUSD", base + 1000)])
    with pytest.raises(ProfileError, match="DLL imports"):
        profile_dataset(c, m)
    result = profile_dataset(c, m, allow_legacy_historical=True)
    assert result["status"] == "PASS"
    assert result["dll_imports_enabled"] is None
    assert result["dll_imports_runtime_verified"] is False
    assert result["instrument_metadata_status"] == "POINT_ONLY_CURRENCIES_UNVERIFIED"
    assert result["point_size"] == 0.001
    assert result["provenance_status"] == "LEGACY_PARTIAL_RUNTIME_SECURITY_AND_CONTRACT_METADATA"


def test_legacy_historical_profile_rejects_invalid_point_size(tmp_path):
    base = 1_800_000_000_000
    c, m = legacy_fixture(tmp_path, [row("XAUUSD", base)])
    data = json.loads(m.read_text())
    data["instrument_point"] = 0
    m.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileError, match="point size"):
        profile_dataset(c, m, allow_legacy_historical=True)
