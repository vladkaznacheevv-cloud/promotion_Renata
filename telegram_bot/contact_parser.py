from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


DEFAULT_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
EMAIL_SEARCH_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
USERNAME_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{3,})")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-\(\)]{8,}\d)")
NAME_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'\-]*")

_NAME_STOPWORDS = {
    "хочу",
    "нужна",
    "нужно",
    "нужен",
    "запрос",
    "ожидания",
    "группа",
    "терапия",
    "консультация",
}


@dataclass(slots=True)
class ParsedContacts:
    name: str | None
    phone: str | None
    email: str | None
    username: str | None

    @property
    def has_any(self) -> bool:
        return bool(self.name or self.phone or self.email or self.username)


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if len(digits) == 11 and digits[0] in {"7", "8"}:
        return f"+7{digits[1:]}"
    if len(digits) == 10:
        return f"+7{digits}"
    if 11 <= len(digits) <= 15:
        return f"+{digits}"
    return None


def _extract_name(lines: list[str], *, email: str | None, phone: str | None, username: str | None) -> str | None:
    def _strip_line(line: str) -> str:
        cleaned = line
        if email:
            cleaned = cleaned.replace(email, " ")
        if username:
            cleaned = cleaned.replace(f"@{username}", " ")
        cleaned = PHONE_RE.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;.-")
        return cleaned.strip()

    candidate = ""
    for line in lines:
        line_candidate = _strip_line(line)
        if line_candidate:
            candidate = line_candidate
            break
    if not candidate:
        return None

    tokens = [token for token in NAME_TOKEN_RE.findall(candidate) if token.lower() not in _NAME_STOPWORDS]
    if not tokens:
        return None
    if len(tokens) >= 2 and tokens[1][:1].isupper():
        return f"{tokens[0]} {tokens[1]}"
    return tokens[0]


def parse_contacts_from_message(text: str | None, *, email_re: Pattern[str] | None = None) -> ParsedContacts:
    raw = str(text or "").replace("\r", "\n")
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if not lines:
        return ParsedContacts(name=None, phone=None, email=None, username=None)

    matcher = email_re or DEFAULT_EMAIL_RE
    email: str | None = None
    for match in EMAIL_SEARCH_RE.findall(raw):
        candidate = match.strip().lower()
        if matcher.match(candidate):
            email = candidate
            break

    username_match = USERNAME_RE.search(raw)
    username = username_match.group(1) if username_match else None

    phone: str | None = None
    for match in PHONE_RE.finditer(raw):
        normalized = normalize_phone(match.group(0))
        if normalized:
            phone = normalized
            break

    name = _extract_name(lines, email=email, phone=phone, username=username)
    return ParsedContacts(name=name, phone=phone, email=email, username=username)

