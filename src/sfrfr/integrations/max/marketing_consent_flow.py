"""Тексты и кнопки запроса marketing consent в MAX."""

from __future__ import annotations

from typing import Any

from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.services.marketing_consent import CONSENT_TEXT_VERSION_MAX, unsubscribe_footer_max

MARKETING_CONSENT_YES = "marketing_consent:yes"
MARKETING_CONSENT_NO = "marketing_consent:no"
MARKETING_CONSENT_UNSUB = "marketing_consent:unsub"

ASK_MARKETING_CONSENT_TEXT = (
    "Иногда мы отправляем полезные материалы о проверке стажа, выписке ИЛС "
    "и новых возможностях сервиса. Это не обязательно для рассмотрения вашего обращения.\n\n"
    "Хотите получать такие сообщения в MAX?"
)

THANKS_GRANTED_TEXT = (
    "Спасибо. Вы согласились получать информационные и рекламные сообщения в MAX "
    "от ООО «Под присмотром» о сервисе «Проверка стажа». "
    "Отписаться можно в любое время: нажмите «Отписаться» или напишите «СТОП»."
)

THANKS_DENIED_TEXT = (
    "Хорошо. Информационные и рекламные сообщения в MAX отправлять не будем. "
    "Сервисные сообщения по вашему обращению могут поступать в рамках выбранного канала связи."
)

REVOKED_TEXT = (
    "Вы отписаны от информационных и рекламных сообщений в MAX.\n"
    "Сервисные сообщения по активному обращению могут поступать только в рамках "
    "выбранного вами канала связи."
)


def marketing_consent_ask_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": "Да, согласен(на)",
                    "payload": MARKETING_CONSENT_YES,
                },
                {
                    "type": "callback",
                    "text": "Нет, не получать",
                    "payload": MARKETING_CONSENT_NO,
                },
            ]
        ]
    )


def marketing_unsub_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": "Отписаться",
                    "payload": MARKETING_CONSENT_UNSUB,
                }
            ]
        ]
    )


def append_unsub_footer(body: str) -> str:
    footer = unsubscribe_footer_max()
    text = (body or "").rstrip()
    if footer.casefold() in text.casefold():
        return text
    return f"{text}\n\n{footer}"


def consent_version() -> str:
    return CONSENT_TEXT_VERSION_MAX
