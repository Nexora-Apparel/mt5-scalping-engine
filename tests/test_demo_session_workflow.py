from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "mt5-demo-session.yml"


def test_demo_session_is_manual_bounded_and_not_always_on():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "timeout-minutes: 135" in source
    assert 'default: "30"' in source
    assert "Start-Sleep -Seconds ($env:SESSION_MINUTES * 60)" in source
    assert "https://download.terminal.free/cdn/web/exness.technologies.ltd/mt5/exness5setup.exe" in source
    assert "download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" not in source
    assert "Start-Process -FilePath $installer" in source
    assert "-Wait -PassThru" in source
    assert "schedule:" not in source
    assert "group: veltrix-demo-data-session" in source
    assert "cancel-in-progress: false" in source


def test_demo_credentials_are_secrets_not_workflow_inputs():
    source = WORKFLOW.read_text(encoding="utf-8")
    inputs = source.split("inputs:", 1)[1].split("permissions:", 1)[0]
    assert "MT5_LOGIN" not in inputs
    assert "MT5_PASSWORD" not in inputs
    assert "MT5_SERVER" not in inputs
    for secret in ("secrets.MT5_LOGIN", "secrets.MT5_PASSWORD", "secrets.MT5_SERVER"):
        assert secret in source


def test_session_disables_automated_trading_and_audits_dataset():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "AllowLiveTrading=0" in source
    assert "EnableDatasetCollection=true" in source
    assert "tools/dataset_integrity.py" in source
    assert "actions/upload-artifact@v4" in source
    assert "ExpectedDemoLogin=" in source
    assert "ExpectedDemoServer=" in source
    assert "Dataset integrity audit failed" in source


def test_startup_failure_emits_terminal_and_expert_diagnostics():
    workflow_source = WORKFLOW.read_text(encoding="utf-8")
    expert_source = (ROOT / "MQL5" / "Experts" / "VeltrixScalper.mq5").read_text(encoding="utf-8")
    assert 'C:\\MT5\\MQL5\\Logs' in workflow_source
    assert 'C:\\MT5\\Logs' in workflow_source
    assert "function Show-MT5Diagnostics" in workflow_source
    assert "Get-Content $file.FullName -Tail 80" in workflow_source
    assert "DATASET ACCOUNT DIAGNOSTIC" in expert_source
    assert "DATASET COLLECTION FAULTED" in expert_source
    assert "DATASET COLLECTION FAULTED" in workflow_source


def test_demo_guard_waits_for_broker_connection_before_reading_account_mode():
    source = (ROOT / "MQL5" / "Experts" / "VeltrixScalper.mq5").read_text(encoding="utf-8")
    assert "for(int attempt=0; attempt<90; attempt++)" in source
    assert "TERMINAL_CONNECTED" in source
    assert "Sleep(1000)" in source
    assert source.index("if(!terminal_connected)") < source.index("if(!demo_mode)")
    assert "broker connection did not complete within 90 seconds" in source
