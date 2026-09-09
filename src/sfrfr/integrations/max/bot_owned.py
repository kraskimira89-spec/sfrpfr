"""Режим bot_owned: клиент ведёт диалог с ботом до «Позвать специалиста»."""

from __future__ import annotations

from typing import Any

from sfrfr.core.config import get_settings

WAITING_FOR_STAFF_TEXT = (
    "Передали запрос специалисту — ответим в этом чате. "
    "Пока ждёте, можно прислать файлы сюда (PDF/JPG/PNG) "
    "или через «Мои документы» на сайте."
)

UPLOAD_ACCEPTED_BOT_OWNED_TEXT = (
    "Спасибо, файл получили и добавили к делу. "
    "Сейчас сверим комплект документов для диагностики."
)


def bot_owned_enabled() -> bool:
    return bool(get_settings().max_bot_owned_enabled)


def is_bot_owned(intake: Any | None) -> bool:
    """True пока флаг on и клиент не нажал «Позвать специалиста»."""
    if not bot_owned_enabled():
        return False
    if intake is None:
        return True
    status = str(getattr(intake, "status", "") or "").strip()
    return status != "handed_to_operator"


def is_handed_to_operator(intake: Any | None) -> bool:
    if intake is None:
        return False
    return str(getattr(intake, "status", "") or "").strip() == "handed_to_operator"
