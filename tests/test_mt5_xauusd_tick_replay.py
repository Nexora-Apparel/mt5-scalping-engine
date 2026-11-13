import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from tools.mt5_xauusd_tick_replay import ReplayError, replay_dataset


ROOT = Path(__file__).resolve().parents[1]


def write_ticks(tmp_path, *, count=420, symbol="XAUUSD"):
    csv_path = tmp_path / "ticks.csv"
    manifest_path = tmp_path / "manifest.json"
    header = ["schema_version","source_id","canonical_symbol","broker_symbol","time_msc","time_utc","bid","ask","last","volume","volume_real","flags"]
    start = 1_800_000_000_000
    rows = []
    price = 3000.0
    for i in range(count):
        stamp = start + 100 + i * 500
        # Deterministic oscillation with a mild drift; quote prices remain valid.
        price += (0.02 if (i // 10) % 3 == 0 else -0.01)
        rows.append({
            "schema_version":"1","source_id":"replay-test","canonical_symbol":symbol,
            "broker_symbol":"XAUUSDm" if symbol=="XAUUSD" else symbol,
            "time_msc":str(stamp),"time_utc":datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat(),
            "bid":f"{price:.3f}","ask":f"{price+0.200:.3f}","last":"0","volume":"0","volume_real":"0","flags":"3",
        })
    with csv_path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=header,lineterminator="\\n")
        writer.writeheader(); writer.writerows(rows)
    manifest={
        "sha256":hashlib.sha256(csv_path.read_bytes()).hexdigest(),"records":len(rows),
        "account_mode":"DEMO","status":"PASS","trading_enabled":False,"dll_imports_enabled":False,
        "instrument_specs":{"XAUUSD":{"point":0.001,"broker_symbol":"XAUUSDm"}},
    }
    manifest_path.write_text(json.dumps(manifest),encoding="utf-8")
    return csv_path,manifest_path


def load_registry_and_config():
    registry=json.loads((ROOT/"research/xauusd_strategy_hypotheses.json").read_text(encoding="utf-8"))
    config=json.loads((ROOT/"research/xauusd_replay_config.json").read_text(encoding="utf-8"))
    return registry,config


def test_replay_is_deterministic_and_execution_disabled(tmp_path):
    csv_path,manifest_path=write_ticks(tmp_path)
    registry,config=load_registry_and_config()
    first=replay_dataset(csv_path,manifest_path,registry,config)
    second=replay_dataset(csv_path,manifest_path,registry,config)
    assert first==second
    assert first["status"]=="PASS"
    assert first["research_only"] is True
    assert first["trade_execution"] is False
    assert first["source_records"]==420
    assert first["holding_horizons_seconds"]==[5,10,15,30,60]
    assert all(event["threshold_history_end_utc"] < event["feature_window_start_utc"] for event in first["events"])


def test_replay_does_not_forward_fill_and_uses_quote_delay_gate(tmp_path):
    csv_path,manifest_path=write_ticks(tmp_path)
    registry,config=load_registry_and_config()
    config["max_quote_delay_ms"]=0
    result=replay_dataset(csv_path,manifest_path,registry,config)
    assert all(event["entry_quote_status"]=="UNAVAILABLE" for event in result["events"])
    assert all(outcome["target_quote_status"]=="ENTRY_QUOTE_UNAVAILABLE" for event in result["events"] for outcome in event["outcomes"])


def test_rejects_xagusd_dataset(tmp_path):
    csv_path,manifest_path=write_ticks(tmp_path,symbol="XAGUSD")
    registry,config=load_registry_and_config()
    with pytest.raises((ProfileError, ReplayError, ValueError)):
        replay_dataset(csv_path,manifest_path,registry,config)


def test_rejects_execution_enabled_config(tmp_path):
    csv_path,manifest_path=write_ticks(tmp_path)
    registry,config=load_registry_and_config()
    config["trade_execution"]=True
    with pytest.raises(ReplayError,match="disable execution"):
        replay_dataset(csv_path,manifest_path,registry,config)
