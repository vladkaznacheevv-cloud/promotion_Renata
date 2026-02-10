from telegram_bot.text_formatting import format_event_card
from telegram_bot.text_utils import looks_like_mojibake, repair_mojibake


def test_event_card_formatting_has_readable_russian():
    event = {
        "title": "РџСЃРёС…РѕР»РѕРіРёСЏ РєРѕРЅС‚Р°РєС‚Р°",
        "description": "РњРёРЅРё-РіСЂСѓРїРїР° РґР»СЏ РїСЂР°РєС‚РёРєРё",
        "date": "2026-02-12",
        "location": "РњРѕСЃРєРІР°",
        "price": 2500,
    }

    text = format_event_card(event)

    assert "Психология контакта" in text
    assert "Мини-группа для практики" in text
    assert "Москва" in text
    assert "2500 ₽" in text
    assert not looks_like_mojibake(text)


def test_utf8_roundtrip_smoke():
    value = "Привет, это проверка UTF-8: мероприятие, оплата, клиент."
    encoded = value.encode("utf-8")
    decoded = encoded.decode("utf-8")
    assert decoded == value
    assert not looks_like_mojibake(decoded)


def test_repair_mojibake_example():
    broken = "РџСЂРёРІРµС‚"
    fixed = repair_mojibake(broken)
    assert fixed == "Привет"
    assert not looks_like_mojibake(fixed)

