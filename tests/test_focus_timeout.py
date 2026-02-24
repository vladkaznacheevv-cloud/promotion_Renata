from telegram_bot.utils import apply_focus_timeout_state


def test_focus_timeout_resets_product_focus_after_30_minutes():
    user_data = {
        "product_focus": "game10",
        "last_user_activity_ts": 1_000.0,
    }
    expired = apply_focus_timeout_state(user_data, now_ts=1_000.0 + 31 * 60)
    assert expired is True
    assert user_data.get("product_focus") is None
    assert user_data["last_user_activity_ts"] == 1_000.0 + 31 * 60


def test_focus_timeout_keeps_focus_when_recent():
    user_data = {
        "product_focus": "gestalt",
        "last_user_activity_ts": 1_000.0,
    }
    expired = apply_focus_timeout_state(user_data, now_ts=1_000.0 + 60)
    assert expired is False
    assert user_data.get("product_focus") == "gestalt"
