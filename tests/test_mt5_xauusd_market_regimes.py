import copy
from datetime import datetime, timezone
import pytest
from tools.mt5_xauusd_market_regimes import RegimeError, classify_regimes


def feature_input(count=80):
    start = 1_800_000_000_000
    rows = []
    for i in range(count):
        rows.append({
            "window_start_utc": datetime.fromtimestamp((start // 5000 + i) * 5, timezone.utc).isoformat(),
            "window_seconds": 5,
            "tick_count": 5 + (i % 9),
            "ticks_per_second": 1.0 + (i % 13) / 4,
            "realized_volatility_bps": 0.2 + (i % 17) / 10,
            "trend_efficiency": (i % 11) / 10,
            "return_bps": ((i % 7) - 3) / 10,
            "spread_points_median": 240.0,
            "spread_points_p95": 240.0,
            "spread_points_max": 240.0,
        })
    return {
        "status": "PASS",
        "research_only": True,
        "feature_schema": "VELTRIX_XAUUSD_TICK_WINDOWS_V1",
        "canonical_symbol": "XAUUSD",
        "source_sha256": "a" * 64,
        "source_records": count * 4,
        "window_seconds": 5,
        "window_count": count,
        "features": rows,
    }


def test_regimes_use_only_preceding_windows():
    data = feature_input()
    result = classify_regimes(data, lookback_windows=30, min_history=20)
    assert result["status"] == "PASS"
    assert result["research_only"] is True
    assert result["regimes"][0]["regime_label"] == "WARMUP"
    assert result["regimes"][19]["regime_label"] == "WARMUP"
    assert result["regimes"][20]["history_count"] == 20
    assert result["regimes"][20]["classification_basis"] == "PAST_WINDOWS_ONLY"
    assert result["classified_windows"] == 60


def test_future_changes_do_not_change_earlier_classifications():
    full = feature_input(80)
    prefix = copy.deepcopy(full)
    prefix["features"] = prefix["features"][:50]
    prefix["window_count"] = 50
    baseline = classify_regimes(prefix, lookback_windows=30, min_history=20)
    full["features"][70]["realized_volatility_bps"] = 99999.0
    full["features"][70]["trend_efficiency"] = 0.999
    changed = classify_regimes(full, lookback_windows=30, min_history=20)
    assert baseline["regimes"] == changed["regimes"][:50]


def test_single_tick_feature_window_remains_unclassified():
    data = feature_input(40)
    row = data["features"][39]
    row.update({
        "tick_count": 1,
        "ticks_per_second": None,
        "realized_volatility_bps": None,
        "trend_efficiency": None,
        "return_bps": None,
    })
    result = classify_regimes(data, lookback_windows=30, min_history=20)
    assert result["regimes"][39]["regime_label"] == "UNCLASSIFIED_CURRENT_DATA"
    assert result["regimes"][39]["thresholds"] is None


@pytest.mark.parametrize("lookback,min_history", [(0, 1), (301, 1), (10, 0), (10, 11), (True, 1)])
def test_rejects_invalid_history_configuration(lookback, min_history):
    with pytest.raises(RegimeError):
        classify_regimes(feature_input(), lookback_windows=lookback, min_history=min_history)


def test_rejects_non_chronological_feature_windows():
    data = feature_input()
    data["features"][5], data["features"][6] = data["features"][6], data["features"][5]
    with pytest.raises(RegimeError, match="chronological"):
        classify_regimes(data)


def test_rejects_wrong_instrument_and_non_research_input():
    data = feature_input()
    data["canonical_symbol"] = "XAGUSD"
    with pytest.raises(RegimeError, match="XAUUSD"):
        classify_regimes(data)
    data = feature_input()
    data["research_only"] = False
    with pytest.raises(RegimeError, match="research-only"):
        classify_regimes(data)
