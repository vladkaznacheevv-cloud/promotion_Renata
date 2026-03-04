from telegram_bot.contact_parser import parse_contacts_from_message


def test_parse_name_and_phone():
    parsed = parse_contacts_from_message("Иван\n+7 (999) 123-45-67")
    assert parsed.name == "Иван"
    assert parsed.phone == "+79991234567"
    assert parsed.email is None
    assert parsed.username is None


def test_parse_name_and_email():
    parsed = parse_contacts_from_message("Анна\nanna@example.com")
    assert parsed.name == "Анна"
    assert parsed.phone is None
    assert parsed.email == "anna@example.com"
    assert parsed.username is None


def test_parse_only_email():
    parsed = parse_contacts_from_message("user@example.com")
    assert parsed.name is None
    assert parsed.phone is None
    assert parsed.email == "user@example.com"
    assert parsed.username is None


def test_parse_only_phone():
    parsed = parse_contacts_from_message("8 999 555 44 33")
    assert parsed.name is None
    assert parsed.phone == "+79995554433"
    assert parsed.email is None
    assert parsed.username is None


def test_parse_name_phone_email():
    parsed = parse_contacts_from_message("Мария, +7 912 000-11-22, maria@example.com")
    assert parsed.name == "Мария"
    assert parsed.phone == "+79120001122"
    assert parsed.email == "maria@example.com"
    assert parsed.username is None


def test_parse_name_and_username():
    parsed = parse_contacts_from_message("Пётр\n@petr_dev")
    assert parsed.name == "Пётр"
    assert parsed.phone is None
    assert parsed.email is None
    assert parsed.username == "petr_dev"
