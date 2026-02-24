from telegram_bot.utils import detect_intent, detect_product_focus, detect_buy_intent


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


def test_detect_product_focus_variants():
    assert detect_product_focus("расскажи про игру 10:0") == "game10"
    assert detect_product_focus("а что по гештальту 1 ступень?") == "gestalt"
    assert detect_product_focus("как зайти в личный кабинет getcourse") == "getcourse"
    assert detect_product_focus("привет, как дела") is None


def test_detect_buy_intent_markers():
    assert detect_buy_intent("сколько стоит и когда старт?")
    assert detect_buy_intent("хочу записаться, как купить?")
    assert not detect_buy_intent("расскажи подробнее про метод")
