from datetime import date, datetime
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_phase8_collection_is_manual_only_and_session_id_bound():
    source = (ROOT / ".github/workflows/veltrix-demo-tick-collection.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "validation_session_id:" in source
    for session_id in (
        "validation_01", "validation_03", "validation_04", "validation_05",
        "validation_06", "validation_07", "validation_08", "validation_09",
        "validation_10", "validation_11", "validation_12", "validation_13",
    ):
        assert session_id in source
    assert "persist-credentials: false" in source
    assert "\\n  schedule:" not in source
    assert "\\n  push:" not in source
    assert "VELTRIX_SESSION_ID:" in source
    assert "XAUUSD-only" in source
    assert "AllowLiveTrading=0" in source
    assert "AllowDllImport=0" in source
    assert "veltrix-exness-demo-ticks-${{ github.run_number }}" in source


def test_phase8_collector_binds_session_id_into_manifest_and_rejects_unknown_ids():
    source = (ROOT / "tools/mt5_demo_tick_collector.py").read_text(encoding="utf-8")
    assert 'session_id = os.environ.get("VELTRIX_SESSION_ID", "")' in source
    assert '"session_id": session_id' in source


def test_phase8_intake_requires_manifest_bound_validation_session_id():
    source = (ROOT / "tools/prepare_xauusd_walk_forward_catalog.py").read_text(encoding="utf-8")
    assert 'manifest.get("session_id") != sid' in source
    assert "manifest session_id does not match" in source
    assert "distinct dates required" in source


def test_phase8_collection_workflow_has_no_trade_execution_or_scheduled_trigger():
    source = (ROOT / ".github/workflows/veltrix-demo-tick-collection.yml").read_text(encoding="utf-8").lower()
    assert "schedule:" not in source
    assert "ordersend(" not in source
    assert "ordersendasync(" not in source
    assert "allowlivetrading=0" in source
    assert "allowdllimport=0" in source



def test_v2_xauusd_collection_calendar_uses_eight_unique_weekdays():
    document = (ROOT / "docs/PHASE8_VALIDATION_V2_PROSPECTIVE_REPLICATION.md").read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| (validation_(?:0[6-9]|1[0-3])) \| (\d{4}-\d{2}-\d{2}) \((Mon|Tue|Wed|Thu|Fri|Sat|Sun)\) \| (\d{2}:\d{2})–(\d{2}:\d{2}) \|",
        document,
        flags=re.MULTILINE,
    )
    assert len(rows) == 8
    assert {row[0] for row in rows} == {f"validation_{i:02d}" for i in range(6, 14)}
    dates = []
    for session_id, date_text, weekday_text, start_text, end_text in rows:
        session_date = date.fromisoformat(date_text)
        assert session_date.weekday() < 5, f"{session_id} is scheduled on a weekend"
        assert session_date.strftime("%a") == weekday_text
        start = datetime.strptime(start_text, "%H:%M")
        end = datetime.strptime(end_text, "%H:%M")
        assert (end - start).total_seconds() == 30 * 60
        dates.append(session_date)
    assert len(set(dates)) == 8


def test_historical_probe_workflow_preserves_provenance_hardening():
    source = (ROOT / ".github/workflows/xauusd-historical-tick-probe.yml").read_text(encoding="utf-8")
    assert "persist-credentials: false" in source
    assert "VELTRIX_SOURCE_COMMIT: ${{ github.sha }}" in source
    assert "VELTRIX_SOURCE_REF: ${{ github.ref_name }}" in source
    assert "MT5_INSTALLER_SIGNER_THUMBPRINT=$($signature.SignerCertificate.Thumbprint)" in source
