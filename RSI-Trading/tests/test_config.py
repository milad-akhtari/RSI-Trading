import math
import pytest

from automation.config import Settings


@pytest.mark.parametrize("overrides", [
    {"max_risk_pct": math.nan}, {"max_total_risk_pct": math.inf},
    {"max_margin_fraction": 2}, {"max_event_age_seconds": 0},
    {"max_quote_age_seconds": -1}, {"max_future_skew_seconds": -1},
    {"max_risk_overrun_pct": -1}, {"deviation_points": -1},
    {"demo_order_submission_enabled": True}, {"execution_mode": "live"},
])
def test_unsafe_config_cannot_start(overrides):
    with pytest.raises(ValueError):
        Settings(webhook_token="test-token", **overrides).validate()


def test_safe_default_template_requires_random_token():
    with pytest.raises(ValueError, match="WEBHOOK_TOKEN"):
        Settings(webhook_token="replace-with-a-long-random-token").validate()


def test_demo_arming_requires_explicit_account_and_server():
    settings = Settings(webhook_token="test-token", demo_order_submission_enabled=True,
                        mt5_login=100000, mt5_server="Fake-Demo")
    settings.validate()
