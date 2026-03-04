from telegram_bot.private_channel_gate import decide_private_channel_join_action


def test_join_request_gate_ignores_other_channel():
    assert (
        decide_private_channel_join_action(
            request_chat_id=-1001,
            configured_channel_id=-1002,
            is_paid=True,
        )
        == "ignore"
    )


def test_join_request_gate_approves_paid_user():
    assert (
        decide_private_channel_join_action(
            request_chat_id=-1001,
            configured_channel_id=-1001,
            is_paid=True,
        )
        == "approve"
    )


def test_join_request_gate_declines_unpaid_user():
    assert (
        decide_private_channel_join_action(
            request_chat_id=-1001,
            configured_channel_id=-1001,
            is_paid=False,
        )
        == "decline"
    )
