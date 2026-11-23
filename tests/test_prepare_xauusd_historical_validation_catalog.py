import pytest

from tools.prepare_xauusd_historical_validation_catalog import (
    EXPECTED_RUN_ID,
    HistoricalIntakeError,
    validate_map,
)


def test_historical_validation_map_accepts_four_preregistered_post_development_dates():
    value = {"sessions": [
        {"session_id": "validation_01", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261116_1730"},
        {"session_id": "validation_02", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261117_1730"},
        {"session_id": "validation_03", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261118_1730"},
        {"session_id": "validation_04", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261119_1730"},
    ]}
    result = validate_map(value)
    assert [item["session_id"] for item in result] == [
        "validation_01", "validation_02", "validation_03", "validation_04"
    ]


def test_historical_validation_map_rejects_duplicate_dates():
    value = {"sessions": [
        {"session_id": "validation_01", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261116_1730"},
        {"session_id": "validation_02", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261116_1730"},
        {"session_id": "validation_03", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261118_1730"},
        {"session_id": "validation_04", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261119_1730"},
    ]}
    with pytest.raises(HistoricalIntakeError, match="distinct dates"):
        validate_map(value)


def test_historical_validation_map_rejects_unregistered_or_wrong_run():
    value = {"sessions": [
        {"session_id": "validation_01", "run_id": EXPECTED_RUN_ID + 1, "interval_id": "ny_20261116_1730"},
        {"session_id": "validation_02", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261117_1730"},
        {"session_id": "validation_03", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261118_1730"},
        {"session_id": "validation_04", "run_id": EXPECTED_RUN_ID, "interval_id": "ny_20261119_1730"},
    ]}
    with pytest.raises(HistoricalIntakeError, match="run ID"):
        validate_map(value)
