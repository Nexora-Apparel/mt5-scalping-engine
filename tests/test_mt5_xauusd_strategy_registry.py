import copy
import json
from pathlib import Path

import pytest

from tools.mt5_xauusd_strategy_registry import RegistryError, validate_registry


REGISTRY_PATH = Path("research/xauusd_strategy_registry_v1.json")


@pytest.fixture
def registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_frozen_registry_passes_and_has_three_candidates(registry):
    result = validate_registry(registry)
    assert result["status"] == "PASS"
    assert result["research_only"] is True
    assert result["candidate_count"] == 3
    assert result["holding_horizons_seconds"] == [5, 15, 30, 60]
    assert result["order_execution_enabled"] is False
    assert result["live_trading_enabled"] is False
    assert result["final_holdout_eligible_development_sessions"] == 0


@pytest.mark.parametrize("symbol", ["XAGUSD", "BTCUSD", "EURUSD", "XAUUSDm"])
def test_rejects_noncanonical_symbols(registry, symbol):
    registry["canonical_symbol"] = symbol
    with pytest.raises(RegistryError, match="XAUUSD"):
        validate_registry(registry)


def test_rejects_any_order_execution_or_live_trading(registry):
    registry["order_execution_enabled"] = True
    with pytest.raises(RegistryError, match="must remain disabled"):
        validate_registry(registry)


def test_rejects_unverified_commission_being_silently_set_to_zero(registry):
    registry["evaluation"]["additional_costs"]["commission"] = 0
    with pytest.raises(RegistryError, match="commission"):
        validate_registry(registry)


def test_rejects_spread_double_counting(registry):
    registry["evaluation"]["executable_quote_convention"]["spread_treatment"] = "Subtract spread again"
    with pytest.raises(RegistryError, match="spread"):
        validate_registry(registry)


def test_rejects_inspected_sessions_as_final_holdout(registry):
    registry["known_development_data"]["holdout_eligible"] = True
    with pytest.raises(RegistryError, match="cannot be holdout"):
        validate_registry(registry)


def test_rejects_duplicate_candidate_ids(registry):
    registry["candidates"][1]["candidate_id"] = registry["candidates"][0]["candidate_id"]
    with pytest.raises(RegistryError, match="unique IDs"):
        validate_registry(registry)


def test_rejects_unregistered_holding_horizon(registry):
    registry["candidates"][0]["horizons_seconds"] = [5, 10, 15, 30, 60]
    with pytest.raises(RegistryError, match="holding horizons changed"):
        validate_registry(registry)


def test_rejects_nonpositive_or_duplicate_parameter_values(registry):
    registry["candidates"][0]["parameter_grid"]["standardized_impulse_threshold"] = [0.5, 0.5]
    with pytest.raises(RegistryError, match="duplicates"):
        validate_registry(registry)


def test_rejects_missing_chronological_leakage_controls(registry):
    registry["data_partition_policy"]["leakage_controls"] = ["random split"]
    with pytest.raises(RegistryError, match="leakage controls"):
        validate_registry(registry)


def test_rejects_approval_of_candidate_before_evaluation(registry):
    registry["decision_policy"]["no_candidate_is_currently_approved"] = False
    with pytest.raises(RegistryError, match="safeguards changed"):
        validate_registry(registry)


def test_rejects_nonresearch_registry_status(registry):
    registry["status"] = "APPROVED"
    with pytest.raises(RegistryError, match="research-only"):
        validate_registry(registry)
