import csv
import hashlib
import json
from datetime import datetime, timezone
import pytest
from tools.mt5_tick_market_profile import HEADER, ProfileError
from tools.mt5_xauusd_feature_research import build_features

def make_row(stamp, bid, ask):
    return {
        "schema_version":"1","source_id":"feature-test","canonical_symbol":"XAUUSD",
        "broker_symbol":"XAUUSDm","time_msc":str(stamp),
        "time_utc":datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat(),
        "bid":str(bid),"ask":str(ask),"last":"0","volume":"0","volume_real":"0","flags":"3",
    }

def write_dataset(tmp_path, rows):
    csv_path=tmp_path/"ticks.csv"; manifest_path=tmp_path/"manifest.json"
    with csv_path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=HEADER,lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    manifest={"sha256":hashlib.sha256(csv_path.read_bytes()).hexdigest(),"records":len(rows),
      "account_mode":"DEMO","status":"PASS","trading_enabled":False,"dll_imports_enabled":False,
      "instrument_specs":{"XAUUSD":{"point":0.001,"broker_symbol":"XAUUSDm"}}}
    manifest_path.write_text(json.dumps(manifest),encoding="utf-8")
    return csv_path,manifest_path

def test_builds_causal_descriptive_windows(tmp_path):
    base=1_800_000_000_000
    csv_path,manifest_path=write_dataset(tmp_path,[
      make_row(base,3000.000,3000.200),make_row(base+1000,3000.100,3000.300),
      make_row(base+2000,3000.200,3000.400),make_row(base+5000,3000.100,3000.300),
      make_row(base+6000,3000.000,3000.200)])
    result=build_features(csv_path,manifest_path,window_seconds=5)
    assert result["status"]=="PASS" and result["research_only"] is True
    assert result["canonical_symbol"]=="XAUUSD" and result["source_records"]==5
    assert result["window_count"]==2
    first,second=result["features"]
    assert first["tick_count"]==3 and first["mid_open"]==3000.1 and first["mid_close"]==3000.3
    assert first["spread_points_median"]==200 and first["trend_efficiency"]==1
    assert second["tick_count"]==2 and second["mid_close"]==3000.1
    assert "traded_volume" not in first and "signal" not in first

@pytest.mark.parametrize("seconds",[0,-1,301,True,1.5])
def test_rejects_invalid_window_width(tmp_path,seconds):
    base=1_800_000_000_000
    csv_path,manifest_path=write_dataset(tmp_path,[make_row(base,3000.0,3000.2)])
    with pytest.raises(ProfileError,match="window_seconds"):
        build_features(csv_path,manifest_path,window_seconds=seconds)

def test_rejects_hash_mismatch_before_feature_generation(tmp_path):
    base=1_800_000_000_000
    csv_path,manifest_path=write_dataset(tmp_path,[make_row(base,3000.0,3000.2)])
    csv_path.write_text(csv_path.read_text(encoding="utf-8")+"\n",encoding="utf-8")
    with pytest.raises(ProfileError,match="SHA-256"):
        build_features(csv_path,manifest_path)

def test_single_tick_window_marks_unobserved_movement_metrics_null(tmp_path):
    base=1_800_000_000_000
    csv_path,manifest_path=write_dataset(tmp_path,[make_row(base,3000.0,3000.2)])
    result=build_features(csv_path,manifest_path,window_seconds=5)
    feature=result["features"][0]
    assert feature["tick_count"]==1
    for field in ("ticks_per_second","return_bps","range_bps","realized_volatility_bps","trend_efficiency","mid_price_change_ratio"):
        assert feature[field] is None
