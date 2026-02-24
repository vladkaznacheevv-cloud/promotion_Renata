from telegram_bot.utils import detect_intent


def test_detect_intent_menu_variants():
    assert detect_intent("меню") == "MENU"
    assert detect_intent("в меню пожалуйста") == "MENU"
    assert detect_intent("START") == "MENU"


def test_detect_intent_manager_variants():
    assert detect_intent("связаться с менеджером") == "MANAGER"
    assert detect_intent("нужны контакты") == "MANAGER"
    assert detect_intent("дайте телефон") == "MANAGER"


def test_detect_intent_sections():
    assert detect_intent("мероприятия на этой неделе") == "EVENTS"
    assert detect_intent("хочу курсы") == "COURSES"
    assert detect_intent("консультация") == "CONSULT"
    assert detect_intent("помощь") == "HELP"
    assert detect_intent("что умеешь") == "HELP"
    assert detect_intent("игра 10:0") == "GAME10"
    assert detect_intent("хочу в закрытый канал") == "GAME10"


def test_detect_intent_unknown():
    assert detect_intent("как справиться с тревогой") is None
