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
    assert '"source_commit_sha": source_commit_sha' in source
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
    assert "VELTRIX_SOURCE_COMMIT_SHA: ${{ github.sha }}" in source
    assert "fetch-depth: 0" in source
    assert "validate_xauusd_v2_collection_dispatch" in source
    assert source.index("Set up 64-bit Python") < source.index("Validate frozen V2 session")


def test_v2_intake_requires_exact_four_unique_session_and_run_ids():
    mapping = {"sessions": [{"session_id": sid, "run_id": 1000 + i} for i, sid in enumerate(V2_IDS)]}
    assert validate_v2_map(mapping) == mapping["sessions"]
    with pytest.raises(ValueError, match="only the four unique V2"):
        validate_v2_map({"sessions": [{"session_id": "validation_01", "run_id": 1}] * 4})
    with pytest.raises(ValueError, match="distinct positive workflow"):
        validate_v2_map({"sessions": [{"session_id": sid, "run_id": 77} for sid in V2_IDS]})


def test_v2_intake_binds_artifact_to_manual_main_workflow_and_frozen_code():
    source = (ROOT / "tools/prepare_xauusd_v2_validation_catalog.py").read_text(encoding="utf-8")
    assert 'run.get("event") != "workflow_dispatch"' in source
    assert 'run.get("path") != ".github/workflows/xauusd-v2-demo-validation-collection.yml"' in source
    assert 'run.get("head_branch") != "main"' in source
    assert 'source_commit != run.get("head_sha")' in source
    assert '"--is-ancestor"' in source


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


def test_frozen_v2_protocol_adapts_only_validation_ids_and_keeps_commission_locked(tmp_path):
    import hashlib
    from tools.mt5_xauusd_v2_protocol import UNVERIFIED_LOCK, load_frozen_v2

    amendment_path = tmp_path / "amendment.json"
    freeze_path = tmp_path / "freeze.json"
    base_path = tmp_path / "base.json"
    registry_path = tmp_path / "registry.json"
    registry_path.write_text('{"registry":"frozen"}', encoding="utf-8")
    registry_hash = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    base = {
        "plan_schema": "VELTRIX_XAUUSD_WALK_FORWARD_PLAN_V1",
        "validation_sessions": ["validation_01", "validation_02", "validation_03", "validation_04"],
        "final_holdout_sessions": [f"holdout_{i:02d}" for i in range(1, 11)],
        "collection_requirements": {},
        "evaluation": {},
    }
    base_path.write_text(json.dumps(base), encoding="utf-8")
    amendment = {
        "plan_schema": "VELTRIX_XAUUSD_WALK_FORWARD_PLAN_V2_AMENDMENT",
        "status": "FROZEN_PREREGISTRATION_RESEARCH_ONLY",
        "source_registry_sha256": registry_hash,
        "new_validation_sessions": [
            {"session_id": sid, "distinct_date_required": True} for sid in V2_IDS
        ],
        "freeze_contract": {"required_fields": [
            "plan_sha256", "implementation_commit_sha", "registry_sha256", "frozen_utc",
            "collection_session_ids", "collection_schedule_utc",
            "commission_evidence_sha256_or_explicit_unverified_lock",
        ]},
    }
    amendment_path.write_text(json.dumps(amendment, sort_keys=True), encoding="utf-8")
    schedule = [
        {"session_id": sid, "start_utc": f"2026-11-{25 + i:02d}T17:30:00Z",
         "end_utc": f"2026-11-{25 + i:02d}T18:00:00Z"}
        for i, sid in enumerate(V2_IDS, start=1)
    ]
    freeze = {
        "plan_sha256": hashlib.sha256(amendment_path.read_bytes()).hexdigest(),
        "implementation_commit_sha": "a" * 40,
        "registry_sha256": registry_hash,
        "frozen_utc": "2026-11-25T16:00:00Z",
        "collection_session_ids": list(V2_IDS),
        "collection_schedule_utc": schedule,
        "commission_evidence_sha256_or_explicit_unverified_lock": UNVERIFIED_LOCK,
    }
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
    plan, _, _ = load_frozen_v2(
        amendment_path=amendment_path, freeze_path=freeze_path,
        base_plan_path=base_path, registry_path=registry_path,
        repo_root=tmp_path, verify_git_ancestry=False,
    )
    assert plan["validation_sessions"] == list(V2_IDS)
    assert plan["final_holdout_sessions"] == base["final_holdout_sessions"]
    assert plan["evaluation"]["commission_status"] == UNVERIFIED_LOCK
    assert plan["evaluation"]["net_performance_allowed"] is False


def test_committed_v2_freeze_binds_validated_code_and_precedes_schedule():
    from tools.mt5_xauusd_v2_protocol import load_frozen_v2

    plan, amendment, freeze = load_frozen_v2(
        amendment_path=ROOT / "research/xauusd_walk_forward_plan_v2_amendment.json",
        freeze_path=ROOT / "research/xauusd_v2_freeze.json",
        base_plan_path=ROOT / "research/xauusd_walk_forward_plan_v1.json",
        registry_path=ROOT / "research/xauusd_strategy_registry_v1.json",
        repo_root=ROOT,
        verify_git_ancestry=True,
    )
    assert amendment["status"] == "FROZEN_PREREGISTRATION_RESEARCH_ONLY"
    assert plan["validation_sessions"] == list(V2_IDS)
    assert plan["v2_protocol"]["freeze_commit_sha"]
    assert freeze["commission_evidence_sha256_or_explicit_unverified_lock"] == "UNVERIFIED_REQUIRED_INPUT"
    assert plan["evaluation"]["net_performance_allowed"] is False
    assert plan["v2_protocol"]["holdout_access"] == "SEALED"


def test_v2_protocol_contract_rejects_execution_or_lane_semantic_drift():
    import copy
    from tools.mt5_xauusd_v2_protocol import validate_amendment_contract

    amendment = json.loads((ROOT / "research/xauusd_walk_forward_plan_v2_amendment.json").read_text(encoding="utf-8"))
    changed = copy.deepcopy(amendment)
    changed["collection_requirements"]["order_submission"] = True
    with pytest.raises(V2ProtocolError, match="collection requirements"):
        validate_amendment_contract(changed)
    changed = copy.deepcopy(amendment)
    changed["position_lane_semantics"]["one_open_position_per_lane"] = False
    with pytest.raises(V2ProtocolError, match="lane semantics"):
        validate_amendment_contract(changed)
