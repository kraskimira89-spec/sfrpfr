"""Разбор ФИО клиента для обращения и шапки чата (RU + латиница).

Не подставляем мусор, ники и случайные символы. При сомнении —
обращение «Клиент» / без ФИО в шапке; лучше переспросить и поправить карточку.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Отчество (кириллица и типичная транслитерация).
_PATRONYMIC_RE = re.compile(
    r"(?i)^(?:"
    r".*(ович|евич|ич|овна|евна|ична|инична)$"
    r"|.*(ovich|evich|ovna|evna|ich)$"
    r")$"
)

# Допустимый токен имени/фамилии: буквы (кир./лат.), дефис, апостроф.
_TOKEN_RE = re.compile(
    r"^[A-Za-zА-Яа-яЁёІіЇїЄєҐґ]"
    r"(?:[A-Za-zА-Яа-яЁёІіЇїЄєҐґ'`’\-]*"
    r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґ])?$"
)

_VOWELS = set("аеёиоуыэюяaeiouyіїєґАЕЁИОУЫЭЮЯAEIOUYІЇЄҐ")

_PLACEHOLDER_RE = re.compile(
    r"(?i)^(max(\s+user)?\s*\d*|клиент|client|user|guest|test|тест|аноним)$"
)

_GIBBERISH_RUN = re.compile(r"(.)\1{3,}")  # aaaa, кккк


@dataclass(frozen=True)
class ParsedPersonName:
    """Результат разбора строки ФИО."""

    raw: str
    surname: str | None = None
    given: str | None = None
    patronymic: str | None = None
    # Уверенность: high / medium / low / none
    confidence: str = "none"
    # Готовое обращение: «Иван Иванович» / «Иван» / «Клиент»
    salutation: str = "Клиент"
    # Для шапки чата / карточки (без мусора); None → «ФИО не указано»
    display: str | None = None
    # Нужно переспросить клиента и поправить карточку
    needs_confirm: bool = True

    @property
    def is_usable(self) -> bool:
        return self.confidence in {"high", "medium"} and bool(self.display)


def is_placeholder_name(value: str | None) -> bool:
    text = " ".join((value or "").split())
    if not text:
        return True
    if "@" in text:
        return True
    if _PLACEHOLDER_RE.match(text):
        return True
    if re.match(r"(?i)^max\s+\d+", text):
        return True
    return False


def _looks_like_token(token: str) -> bool:
    t = token.strip()
    if len(t) < 2 or len(t) > 40:
        return False
    if not _TOKEN_RE.match(t):
        return False
    if any(ch.isdigit() for ch in t):
        return False
    if _GIBBERISH_RUN.search(t):
        return False
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 2:
        return False
    # Слишком мало гласных для «слова» (случайный набор согласных).
    vowels = sum(1 for c in letters if c in _VOWELS)
    if len(letters) >= 4 and vowels == 0:
        return False
    if len(letters) >= 6 and vowels / len(letters) < 0.15:
        return False
    # Смесь кириллицы и латиницы в одном токене — сомнительно.
    has_cyr = any("А" <= c.upper() <= "Я" or c in "ЁёІіЇїЄєҐґ" for c in letters)
    has_lat = any("A" <= c.upper() <= "Z" for c in letters)
    if has_cyr and has_lat:
        return False
    return True


def is_plausible_name_token(token: str | None) -> bool:
    return _looks_like_token(token or "")


def looks_like_patronymic(token: str | None) -> bool:
    t = (token or "").strip()
    if not t or not _looks_like_token(t):
        return False
    return bool(_PATRONYMIC_RE.match(t))


def _title_case_token(token: str) -> str:
    """Аккуратная капитализация без ломания «ё» / дефисов."""
    parts = re.split(r"([-'`’])", token)
    out: list[str] = []
    for part in parts:
        if part in "-'`’" or not part:
            out.append(part)
            continue
        out.append(part[:1].upper() + part[1:].lower())
    return "".join(out)


def _clean_tokens(full_name: str | None) -> list[str]:
    raw = " ".join((full_name or "").replace(",", " ").split())
    if not raw or is_placeholder_name(raw):
        return []
    tokens = [p for p in re.split(r"\s+", raw) if p]
    good = [_title_case_token(t) for t in tokens if _looks_like_token(t)]
    # Если больше половины токенов мусор — не доверяем строке целиком.
    if tokens and len(good) < max(1, (len(tokens) + 1) // 2):
        return []
    return good


def _is_cyrillic_word(token: str) -> bool:
    return any("А" <= c.upper() <= "Я" or c in "ЁёІіЇїЄєҐґ" for c in token)


def parse_person_name(full_name: str | None) -> ParsedPersonName:
    """Разобрать ФИО; при сомнении salutation=Клиент, display=None."""
    raw = " ".join((full_name or "").split())
    if not raw or is_placeholder_name(raw):
        return ParsedPersonName(raw=raw, confidence="none", needs_confirm=True)

    tokens = _clean_tokens(raw)
    if not tokens:
        return ParsedPersonName(raw=raw, confidence="none", needs_confirm=True)

    surname: str | None = None
    given: str | None = None
    patronymic: str | None = None
    confidence = "medium"

    if len(tokens) >= 3 and looks_like_patronymic(tokens[2]):
        # Канон РФ: Фамилия Имя Отчество
        surname, given, patronymic = tokens[0], tokens[1], tokens[2]
        confidence = "high"
        if len(tokens) > 3:
            confidence = "medium"
    elif len(tokens) == 2 and looks_like_patronymic(tokens[1]):
        # Имя Отчество без фамилии
        given, patronymic = tokens[0], tokens[1]
        confidence = "high"
    elif len(tokens) == 2:
        a, b = tokens[0], tokens[1]
        if _is_cyrillic_word(a) or _is_cyrillic_word(b):
            # Карточка РФ: Фамилия Имя
            surname, given = a, b
        else:
            # Латиница из мессенджера: Given Surname
            given, surname = a, b
        confidence = "medium"
    elif len(tokens) == 1:
        given = tokens[0]
        confidence = "medium" if len(tokens[0]) >= 2 else "low"
    else:
        surname, given = tokens[0], tokens[1]
        if looks_like_patronymic(tokens[2]):
            patronymic = tokens[2]
            confidence = "high"
        else:
            confidence = "low"

    if confidence == "low" or not given:
        return ParsedPersonName(
            raw=raw,
            surname=surname,
            given=given,
            patronymic=patronymic,
            confidence="low",
            salutation="Клиент",
            display=None,
            needs_confirm=True,
        )

    if given and patronymic:
        salutation = f"{given} {patronymic}"
    elif given:
        salutation = given
    else:
        salutation = "Клиент"

    display_parts = [p for p in (surname, given, patronymic) if p]
    # Для латиницы Given Surname показываем в привычном порядке имени.
    if (
        surname
        and given
        and not patronymic
        and not (_is_cyrillic_word(surname) or _is_cyrillic_word(given))
    ):
        display_parts = [given, surname]
    display = " ".join(display_parts) if display_parts else None

    return ParsedPersonName(
        raw=raw,
        surname=surname,
        given=given,
        patronymic=patronymic,
        confidence=confidence,
        salutation=salutation if salutation else "Клиент",
        display=display,
        needs_confirm=confidence != "high",
    )


def client_salutation(full_name: str | None) -> str:
    """Обращение: имя+отчество / имя / «Клиент»."""
    return parse_person_name(full_name).salutation


def display_person_name(full_name: str | None) -> str | None:
    """ФИО для шапки чата; None если нельзя уверенно показать."""
    return parse_person_name(full_name).display


def welcome_first_name(full_name: str | None) -> str | None:
    """Только имя для «Здравствуйте, …!» — без фамилии и мусора."""
    parsed = parse_person_name(full_name)
    if not parsed.is_usable:
        return None
    return parsed.given


def should_accept_incoming_display_name(
    current: str | None,
    incoming: str | None,
) -> bool:
    """Записать имя из MAX только поверх заглушки и только если токен правдоподобен."""
    if is_placeholder_name(incoming) or not incoming:
        return False
    parsed = parse_person_name(incoming)
    if not parsed.is_usable or not parsed.given:
        return False
    # Одно слово из профиля MAX — ок; длинный мусор — нет.
    tokens = _clean_tokens(incoming)
    if len(tokens) > 3:
        return False
    return is_placeholder_name(current) or not (current or "").strip()
