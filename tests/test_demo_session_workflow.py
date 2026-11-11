from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "mt5-demo-session.yml"


def test_demo_session_is_manual_bounded_and_not_always_on():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "timeout-minutes: 135" in source
    assert 'default: "120"' in source
    assert "Start-Sleep -Seconds ($env:SESSION_MINUTES * 60)" in source
    assert "schedule:" not in source


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
