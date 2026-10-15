from mt5_scalping.health import HealthResult


def test_not_checked_health_is_explicitly_read_only():
    result = HealthResult.not_checked(False, False)
    assert result.connection_state == "not_checked"
    assert result.quote_state == "not_checked"
    assert "No orders were submitted" in result.details
