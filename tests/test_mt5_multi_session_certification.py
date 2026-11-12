import csv,hashlib,json
from datetime import datetime,timedelta,timezone
import pytest
from tools.mt5_multi_session_certification import certify_sessions
from tools.mt5_tick_market_profile import HEADER,ProfileError

def make_session(tmp_path,name,start_ms):
    c,m=tmp_path/f"{name}.csv",tmp_path/f"{name}.json";rows=[]
    for off in (0,1000,2000):
        stamp=start_ms+off
        rows.append({"schema_version":"1","source_id":name,"canonical_symbol":"XAUUSD",
          "broker_symbol":"XAUUSDm","time_msc":str(stamp),
          "time_utc":datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat(),
          "bid":"3000.0","ask":"3000.2","last":"3000.1","volume":"1","volume_real":"1.0","flags":"3"})
    with c.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=HEADER,lineterminator="\n");w.writeheader();w.writerows(rows)
    start=datetime.fromtimestamp(start_ms/1000,timezone.utc);end=start+timedelta(seconds=1800,milliseconds=50)
    m.write_text(json.dumps({"sha256":hashlib.sha256(c.read_bytes()).hexdigest(),"records":len(rows),
      "account_mode":"DEMO","status":"PASS","trading_enabled":False,"dll_imports_enabled":False,
      "duration_clock":"monotonic","duration_seconds":1800.05,"collection_started_utc":start.isoformat(),
      "collection_ended_utc":end.isoformat(),"instrument_specs":{"XAUUSD":{"point":0.001,"broker_symbol":"XAUUSDm"}}}))
    return c,m

def test_requires_two_sessions(tmp_path):
    with pytest.raises(ProfileError,match="at least two"): certify_sessions([make_session(tmp_path,"a",1800000000000)])

def test_aggregates_xauusd_sessions_only(tmp_path):
    r=certify_sessions([make_session(tmp_path,"a",1800000000000),make_session(tmp_path,"b",1800003000000)])
    assert r["status"]=="PASS" and r["session_count"]==2
    assert set(r["symbols"])=={"XAUUSD"} and r["symbols"]["XAUUSD"]["sessions"]==2

def test_rejects_duplicate_and_overlapping_sessions(tmp_path):
    a=make_session(tmp_path,"a",1800000000000)
    with pytest.raises(ProfileError,match="duplicate dataset"): certify_sessions([a,a])
    b=make_session(tmp_path,"b",1800000600000)
    with pytest.raises(ProfileError,match="overlapping collection intervals"): certify_sessions([a,b])

def test_rejects_short_duration(tmp_path):
    a=make_session(tmp_path,"a",1800000000000);b=make_session(tmp_path,"b",1800003000000)
    d=json.loads(b[1].read_text());d["duration_seconds"]=1799;b[1].write_text(json.dumps(d))
    with pytest.raises(ProfileError,match="shorter than 30 minutes"): certify_sessions([a,b])
