from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.mt5_xauusd_v2_protocol import V2_IDS, V2ProtocolError
from tools.prepare_xauusd_v2_validation_catalog import validate_v2_map

ROOT = Path(__file__).resolve().parents[1]


def test_v2_collector_is_restricted_to_four_new_ids_and_explicitly_read_only():
    source = (ROOT / "tools/mt5_demo_tick_collector_v2.py").read_text(encoding="utf-8")
    assert 'f"v2_validation_{i:02d}" for i in range(1, 5)' in source
    assert '"order_submission": False' in source
    assert '"position_management": False' in source
    assert '"execution_enabled": False' in source
    assert "validation_01 or validation_03" not in source


def test_v2_collection_workflow_is_manual_and_uses_dispatch_commit():
    source = (ROOT / ".github/workflows/xauusd-v2-demo-validation-collection.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "schedule:" not in source
    assert "ref: ${{ github.sha }}" in source
    for sid in V2_IDS:
        assert sid in source
    assert "- validation_01" not in source
    assert "mt5_demo_tick_collector_v2.py" in source
    assert "AllowLiveTrading=0" in source
    assert "AllowDllImport=0" in source
    assert "ordersend(" not in source.lower()
    assert "ordersendasync(" not in source.lower()


def test_v2_intake_requires_exact_four_unique_session_and_run_ids():
    mapping = {"sessions": [{"session_id": sid, "run_id": 1000 + i} for i, sid in enumerate(V2_IDS)]}
    assert validate_v2_map(mapping) == mapping["sessions"]
    with pytest.raises(ValueError, match="only the four unique V2"):
        validate_v2_map({"sessions": [{"session_id": "validation_01", "run_id": 1}] * 4})
    with pytest.raises(ValueError, match="distinct positive workflow"):
        validate_v2_map({"sessions": [{"session_id": sid, "run_id": 77} for sid in V2_IDS]})


def test_v2_evaluator_requires_frozen_protocol_and_rejects_v1_ids():
    source = (ROOT / "tools/mt5_xauusd_v2_validation.py").read_text(encoding="utf-8")
    assert "load_frozen_v2(" in source
    assert "all four frozen V2 validation sessions" in source
    assert "V1 validation sessions are prohibited" in source
    assert '"net_performance_allowed" = False' not in source
    assert 'result["net_performance_allowed"] = False' in source


def test_v2_freeze_verifier_rejects_draft_amendment(tmp_path):
    amendment = tmp_path / "amendment.json"
    freeze = tmp_path / "freeze.json"
    base = tmp_path / "base.json"
    registry = tmp_path / "registry.json"
    amendment.write_text(json.dumps({
        "plan_schema": "VELTRIX_XAUUSD_WALK_FORWARD_PLAN_V2_AMENDMENT",
        "status": "DRAFT_PREREGISTRATION_NOT_FROZEN",
    }))
    freeze.write_text("{}")
    base.write_text("{}")
    registry.write_text("{}")
    from tools.mt5_xauusd_v2_protocol import load_frozen_v2
    with pytest.raises(V2ProtocolError, match="not frozen"):
        load_frozen_v2(
            amendment_path=amendment, freeze_path=freeze,
            base_plan_path=base, registry_path=registry,
            repo_root=tmp_path, verify_git_ancestry=False,
        )
