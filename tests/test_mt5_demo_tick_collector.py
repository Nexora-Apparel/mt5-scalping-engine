import csv,importlib.util
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
import pytest
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools"/"mt5_demo_tick_collector.py"
spec=importlib.util.spec_from_file_location("mt5_demo_tick_collector",P)
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)

class Clock:
 def __init__(self): self.mono=100.0;self.epoch_ms=1800000000000
 def monotonic(self): return self.mono
 def now(self): return datetime.fromtimestamp(self.epoch_ms/1000,tz=timezone.utc)
 def sleep(self,s): self.mono+=s;self.epoch_ms+=int(s*1000)

class FakeMT5:
 COPY_TICKS_ALL=3
 def __init__(self,c): self.clock=c;self.shutdown_called=False
 def initialize(self,*a,**k): return True
 def terminal_info(self): return SimpleNamespace(connected=True,trade_allowed=False,dlls_allowed=False)
 def account_info(self): return SimpleNamespace(login=12345678,server="Exness-MT5Trial",trade_mode=0,company="Exness")
 def symbols_get(self): return [SimpleNamespace(name="XAUUSDm",currency_base="XAU",currency_profit="USD"),
                                SimpleNamespace(name="XAGUSDm",currency_base="XAG",currency_profit="USD")]
 def symbol_select(self,s,e): return e and s=="XAUUSDm"
 def symbol_info(self,s): return SimpleNamespace(point=0.01,digits=2)
 def symbol_info_tick(self,s): return SimpleNamespace(bid=3000.0,ask=3000.2,time_msc=int(self.clock.now().timestamp()*1000))
 def copy_ticks_from(self,s,d,n,f): return [SimpleNamespace(time_msc=int(self.clock.now().timestamp()*1000),bid=3000.0,ask=3000.2,last=3000.1,volume=1,volume_real=1.0,flags=f)]
 def last_error(self): return (1,"fake")
 def shutdown(self): self.shutdown_called=True

def valid_row(symbol="XAUUSD",stamp=1800000000000):
 return {"schema_version":"1","source_id":"test","canonical_symbol":symbol,"broker_symbol":symbol+"m",
 "time_msc":stamp,"time_utc":collector.utc_iso(stamp),"bid":"3000.0","ask":"3000.2",
 "last":"3000.1","volume":"1.0","volume_real":"1.0","flags":3}

def write(path,rows):
 with path.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=collector.HEADER,lineterminator="\n");w.writeheader();w.writerows(rows)

def test_audit_is_xauusd_only_and_hashes_dataset(tmp_path):
 p=tmp_path/"ticks.csv";write(p,[valid_row()])
 r=collector.audit_ticks(p);assert r["data_audit_status"]=="PASS"
 assert set(r["streams"])=={"XAUUSD"} and r["records"]==1
 p=tmp_path/"silver.csv";write(p,[valid_row("XAGUSD")])
 with pytest.raises(collector.DiagnosticFailure,match="unexpected canonical symbol"): collector.audit_ticks(p)

def test_audit_rejects_duplicate_and_out_of_order(tmp_path):
 p=tmp_path/"bad.csv";row=valid_row();write(p,[row,row])
 with pytest.raises(collector.DiagnosticFailure,match="duplicate tick"): collector.audit_ticks(p)
 write(p,[valid_row(stamp=1800000000100),valid_row(stamp=1800000000000)])
 with pytest.raises(collector.DiagnosticFailure,match="moved backwards"): collector.audit_ticks(p)

def test_collector_requires_bounded_30_minutes():
 with pytest.raises(collector.DiagnosticFailure,match="only the bounded 30-minute"): collector.collect(object(),60,Path("unused"))

class DriftClock(Clock):
 def now(self):
  value=super().now()
  if self.mono>=1901: value-=timedelta(milliseconds=19)
  return value

def test_full_collector_records_only_gold_and_passes_integrity(tmp_path,monkeypatch):
 c=DriftClock();api=FakeMT5(c)
 for k,v in {"MT5_LOGIN":"12345678","MT5_PASSWORD":"fake","MT5_SERVER":"Exness-MT5Trial","MT5_TERMINAL":r"C:\MT5\terminal64.exe" ,"VELTRIX_SESSION_ID":"validation_01"}.items(): monkeypatch.setenv(k,v)
 m=collector.collect(api,30,tmp_path,monotonic=c.monotonic,sleep=c.sleep,now=c.now)
 assert api.shutdown_called and m["duration_seconds"]==1802.0 and m["status"]=="PASS"
 assert m["account_mode"]=="DEMO" and m["trading_enabled"] is False and m["dll_imports_enabled"] is False
 assert m["session_id"]=="validation_01"
 assert set(m["symbols"])=={"XAUUSD"} and set(m["streams"])=={"XAUUSD"}
 assert m["streams"]["XAUUSD"]["records"]==1802
 assert (tmp_path/"manifest.json").is_file() and (tmp_path/"veltrix_exness_demo_ticks.csv").is_file()

def test_collector_contains_no_order_submission_calls():
 import re
 source=P.read_text()
 for pat in (r"\bmt5\.order_send\s*\(",r"\bmt5\.order_check\s*\(",r"\bmt5\.order_send_async\s*\(",r"\bmt5\.positions_get\s*\(",r"\bmt5\.orders_get\s*\("):
  assert not re.search(pat,source)

def test_warmup_requires_five_consecutive_gold_quotes():
 c=Clock();api=FakeMT5(c)
 symbols={"XAUUSD":"XAUUSDm"}
 q=collector.wait_for_fresh_quotes(api,symbols,12345678,"Exness-MT5Trial",timeout_seconds=15,
  stable_samples_required=5,monotonic=c.monotonic,sleep=c.sleep,now=c.now)
 assert len(q)==1 and q[0]["canonical"]=="XAUUSD"

def test_warmup_fails_closed_when_gold_quote_stays_stale():
 c=Clock();api=FakeMT5(c)
 api.symbol_info_tick=lambda s: SimpleNamespace(bid=3000.0,ask=3000.2,time_msc=int(c.now().timestamp()*1000)-60000)
 with pytest.raises(collector.DiagnosticFailure,match="fresh quote warm-up failed"):
  collector.wait_for_fresh_quotes(api,{"XAUUSD":"XAUUSDm"},12345678,"Exness-MT5Trial",
   timeout_seconds=3,stable_samples_required=2,monotonic=c.monotonic,sleep=c.sleep,now=c.now)
