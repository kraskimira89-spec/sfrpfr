"""Чек-лист «Как самому проверить стаж» после анкеты (ТЗ-35 B2): отправка на e-mail."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sfrfr.integrations.max import questionnaire as q
from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store
from sfrfr.services.lead_magnet_checklist import (
    LEAD_MAGNET_BOT_URL,
    LEAD_MAGNET_PDF_URL,
    LEAD_MAGNET_PRINT_URL,
    build_lead_magnet_after_start_message,
)

logger = logging.getLogger(__name__)

Reply = Callable[[str, list[dict[str, Any]] | None], Any]

CHECKLIST_TITLE = "Как самому проверить стаж"
CALLBACK_PREFIX = "lm:"
SEND = "lm:send"
HAVE = "lm:have"
USE_KNOWN = "lm:use_known"
CANCEL = "lm:cancel"
MAX_SENDS = 3

OFFER_TEXT = (
    f"Хотите бесплатный чек-лист «{CHECKLIST_TITLE}»? "
    "Пришлём его на e-mail: какие документы взять и как сверить периоды стажа."
)
ASK_EMAIL_TEXT = "Напишите e-mail, на который прислать чек-лист."
INVALID_EMAIL_TEXT = "Похоже, в адресе ошибка. Пример: ivanova@yandex.ru. Напишите e-mail ещё раз."
HAVE_TEXT = "Хорошо. Когда документы будут под рукой — пришлите их прямо в этот чат, фото или PDF."
CANCEL_TEXT = "Хорошо, не отправляем. Чек-лист можно запросить позже командой /checklist."
LIMIT_TEXT = (
    "Чек-лист уже отправлен несколько раз. Если письма нет — проверьте папку «Спам» "
    "или напишите «Нужен чек-лист», пришлём его сюда в чат."
)
EMAIL_SUBJECT = f"Чек-лист «{CHECKLIST_TITLE}» — Проверка стажа"


def offer_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [
                {"type": "callback", "text": "Прислать", "payload": SEND},
                {"type": "callback", "text": "Уже получал", "payload": HAVE},
            ]
        ]
    )


def _ask_keyboard(known_email: str) -> list[dict[str, Any]]:
    rows: list[list[dict[str, Any]]] = []
    if known_email:
        rows.append(
            [{"type": "callback", "text": f"Отправить на {known_email}", "payload": USE_KNOWN}]
        )
    rows.append([{"type": "callback", "text": "Не нужно", "payload": CANCEL}])
    return inline_buttons_keyboard(rows)


def build_email_body(*, first_name: str | None = None) -> str:
    """Текст письма. Без слов, которые вырезает redact_outbound_body."""
    greeting = f"Здравствуйте, {first_name}!" if (first_name or "").strip() else "Здравствуйте!"
    return (
        f"{greeting}\n\n"
        f"Высылаем бесплатный чек-лист «{CHECKLIST_TITLE}».\n\n"
        "1) Закажите на Госуслугах выписку из ИЛС (сведения о стаже) — актуальную, "
        "с датой формирования.\n"
        "2) Возьмите трудовую книжку (бумажную) или выписку из электронной трудовой.\n"
        "3) Сверьте периоды: все ли места работы есть в выписке и совпадают ли даты.\n"
        "4) Если периода нет или даты расходятся — это повод разобраться подробнее.\n\n"
        f"PDF (одна страница A4): {LEAD_MAGNET_PDF_URL}\n"
        f"Рабочая тетрадь на 8 страниц: {LEAD_MAGNET_PRINT_URL}\n\n"
        f"Нашли расхождение — пришлите выписку и трудовую в чат-бот MAX: {LEAD_MAGNET_BOT_URL}\n\n"
        "Мы готовим документы, проект обращения и план — расскажем по шагам, "
        "но подаёте через СФР или Госуслуги вы сами. Решение принимает только СФР.\n\n"
        "Личные документы в ответ на это письмо не присылайте — только в чат-бот MAX "
        "или в кабинет на сайте. Вопросы: proverkastaza@yandex.ru"
    )


def send_checklist_email(*, to: str, first_name: str | None = None) -> bool:
    try:
        from sfrfr.integrations.yandex_workspace.mail import send_mail

        result = send_mail(
            to=to,
            template="custom",
            subject=EMAIL_SUBJECT,
            body=build_email_body(first_name=first_name),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("checklist email failed: %s", exc)
        return False
    if not result.get("ok"):
        logger.warning("checklist email not sent: %s", result.get("error") or result.get("reason"))
        return False
    return True


def is_active(rec: MaxIntakeRecord | None) -> bool:
    return rec is not None and rec.lm_step == "email"


def _deliver(
    rec: MaxIntakeRecord, reply: Reply, *, email: str, log_event: Callable[[str], Any]
) -> tuple[str, str]:
    rec.lm_step = None
    if rec.lm_send_count >= MAX_SENDS:
        get_intake_store().save(rec)
        reply(LIMIT_TEXT, None)
        return "checklist_email_limit", LIMIT_TEXT
    first_name = (rec.q_answers or {}).get("first_name")
    if send_checklist_email(to=email, first_name=first_name):
        rec.lm_send_count += 1
        rec.lm_sent_at = datetime.now(UTC).isoformat()
        get_intake_store().save(rec)
        log_event(f"Чек-лист «{CHECKLIST_TITLE}» отправлен на e-mail {email}")
        text = (
            f"Отправили чек-лист «{CHECKLIST_TITLE}» на {email}. "
            "Если письма нет через 10 минут — проверьте папку «Спам»."
        )
        reply(text, None)
        return "checklist_email_sent", text
    get_intake_store().save(rec)
    text = (
        "Не получилось отправить письмо. Вот чек-лист здесь, в чате:\n\n"
        + build_lead_magnet_after_start_message(name=first_name)
    )
    reply(text, None)
    return "checklist_email_failed", text


def handle(
    rec: MaxIntakeRecord,
    reply: Reply,
    *,
    text: str,
    payload: str,
    log_event: Callable[[str], Any],
) -> tuple[str, str] | None:
    """Кнопки lm:* и ввод e-mail. None — не наш апдейт."""
    known = (rec.q_answers or {}).get("email") or ""
    if payload == HAVE:
        rec.lm_step = None
        get_intake_store().save(rec)
        reply(HAVE_TEXT, None)
        return "checklist_have", HAVE_TEXT
    if payload == CANCEL:
        rec.lm_step = None
        get_intake_store().save(rec)
        reply(CANCEL_TEXT, None)
        return "checklist_cancel", CANCEL_TEXT
    if payload == SEND:
        rec.lm_step = "email"
        get_intake_store().save(rec)
        reply(ASK_EMAIL_TEXT, _ask_keyboard(known))
        return "checklist_ask_email", ASK_EMAIL_TEXT
    if payload == USE_KNOWN and known:
        return _deliver(rec, reply, email=known, log_event=log_event)
    if payload or not is_active(rec):
        return None
    email = q.clean_email(text)
    if email is None:
        reply(INVALID_EMAIL_TEXT, _ask_keyboard(known))
        return "checklist_email_invalid", INVALID_EMAIL_TEXT
    return _deliver(rec, reply, email=email, log_event=log_event)
