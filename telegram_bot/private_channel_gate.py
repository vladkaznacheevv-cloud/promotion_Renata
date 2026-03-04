from __future__ import annotations


def decide_private_channel_join_action(
    *,
    request_chat_id: int | str | None,
    configured_channel_id: int | str | None,
    is_paid: bool,
) -> str:
    if configured_channel_id not in (None, "") and request_chat_id is not None:
        if str(request_chat_id) != str(configured_channel_id):
            return "ignore"
    return "approve" if is_paid else "decline"
