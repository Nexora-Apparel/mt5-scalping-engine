import json
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "research" / "xauusd_strategy_hypotheses.json"


def test_hypothesis_registry_is_xauusd_only_and_unexecuted():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert data["instrument"] == "XAUUSD"
    assert data["status"] == "PREREGISTERED_UNTESTED"
    assert data["evaluation_policy"]["trade_execution"] is False
    assert data["threshold_policy"]["current_window_excluded"] is True
    assert data["threshold_policy"]["future_windows_excluded"] is True
    assert data["threshold_policy"]["session_history_reset"] is True


def test_hypotheses_have_unique_ids_and_user_holding_horizons():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    ids = [item["id"] for item in data["hypotheses"]]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 2
    assert data["holding_horizons_seconds"] == [5, 10, 15, 30, 60]
    for item in data["hypotheses"]:
        assert item["status"] == "UNTESTED"
        assert item["evaluation_horizons_seconds"] == data["holding_horizons_seconds"]
        assert item["entry_context"]
        assert item["direction"]
        assert item["invalidation_reference"]
        assert item["primary_outcome"]


def test_registry_forbids_execution_and_non_xauusd_scope():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    prohibitions = " ".join(data["prohibitions"]).lower()
    assert "xagusd" in prohibitions
    assert "trade signals" in prohibitions
    assert "order placement" in prohibitions
    assert "production deployment" in prohibitions
    assert "telegram activation" in prohibitions
