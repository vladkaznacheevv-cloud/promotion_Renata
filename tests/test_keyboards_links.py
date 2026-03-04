from telegram_bot.keyboards import GETCOURSE_CABINET_URL, get_courses_empty_kb


def test_getcourse_button_uses_main_site_url():
    markup = get_courses_empty_kb()
    assert GETCOURSE_CABINET_URL == "https://renataminakova.ru"
    assert markup.inline_keyboard[0][0].url == "https://renataminakova.ru"
