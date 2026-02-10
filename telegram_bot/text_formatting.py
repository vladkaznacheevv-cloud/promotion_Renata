from __future__ import annotations

from telegram_bot.text_utils import normalize_text_for_telegram


def format_event_card(event: dict) -> str:
    title = normalize_text_for_telegram(event.get("title")) or "Без названия"
    date_part = normalize_text_for_telegram(event.get("date")) or "дата уточняется"
    location = normalize_text_for_telegram(event.get("location")) or "—"
    description = normalize_text_for_telegram(event.get("description"))
    link_getcourse = normalize_text_for_telegram(event.get("link_getcourse"))

    price_part = event.get("price")
    price_text = f"{int(price_part)} ₽" if price_part not in (None, "", 0) else "по запросу"

    lines = [
        f"*{title}*",
        f"🗓 {date_part}",
        f"📍 {location}",
        f"💳 {price_text}",
    ]
    if description:
        lines.append("")
        lines.append(normalize_text_for_telegram(description) or "")
    if link_getcourse:
        lines.append("")
        lines.append(f"GetCourse: {link_getcourse}")
    return "\n".join(lines)
