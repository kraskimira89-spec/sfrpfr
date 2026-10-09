"""Выбор после анкеты: диагностика 3 000 ₽ или чек-лист (clarity-funnel §4)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sfrfr.core.copy import OFFER_URL, PAYMENT_LEGAL_ACCEPTANCE
from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store

Reply = Callable[[str, list[dict[str, Any]] | None], Any]

CALLBACK_PREFIX = "diag:"
YES = "diag:yes"
CHECKLIST = "diag:checklist"
_STEP_KEY = "_diag_step"
OFFER_VERSION = "offer-2026-09-09"

OFFER_TEXT = (
    "По ответам анкеты можно выбрать следующий шаг.\n\n"
    "Есть два пути: начать самостоятельно по бесплатному чек-листу "
    "или оформить диагностику — сверку документов и письменный план.\n"
    "Стоимость диагностики — 3 000 рублей. "
    "Решение по пенсии принимает только СФР.\n\n"
    "Оформляем диагностику или пока остановимся на чек-листе?"
)

CONFIRM_TEXT = (
    "Спасибо. Оформляем диагностику документов. Стоимость — 3 000 рублей.\n"
    f"{PAYMENT_LEGAL_ACCEPTANCE} Оферта: {OFFER_URL}\n"
    "После оплаты пришлите выписку ИЛС и трудовую (или сведения о трудовой) "
    "прямо в этот чат — PDF или фото."
)

NO_CASE_TEXT = (
    "Чтобы оформить диагностику, сначала нажмите «Начать» в меню бота "
    "или напишите «Нужна проверка» — подготовим счёт и ссылку на оплату здесь, в чате."
)

CONSENT_NEEDED_TEXT = (
    "Перед оформлением диагностики нужно согласие на обработку персональных данных. "
    "Нажмите кнопку согласия в чате — затем снова «Оформить диагностику»."
)

FAIL_TEXT = (
    "Сейчас не получилось сразу выставить счёт. "
    "Напишите «Нужна проверка» или позовите специалиста — поможем оформить оплату в чате."
)


def offer_keyboard() -> list[dict[str, Any]]:
    return inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": "Оформить диагностику 3 000 ₽",
                    "payload": YES,
                }
            ],
            [
                {
                    "type": "callback",
                    "text": "Пока чек-лист",
                    "payload": CHECKLIST,
                }
            ],
        ]
    )


def is_pending(rec: MaxIntakeRecord | None) -> bool:
    if rec is None:
        return False
    return (rec.q_answers or {}).get(_STEP_KEY) == "pending"


def mark_pending(rec: MaxIntakeRecord) -> None:
    answers = dict(rec.q_answers or {})
    answers[_STEP_KEY] = "pending"
    rec.q_answers = answers
    get_intake_store().save(rec)


def clear_pending(rec: MaxIntakeRecord) -> None:
    answers = dict(rec.q_answers or {})
    answers.pop(_STEP_KEY, None)
    rec.q_answers = answers
    get_intake_store().save(rec)


def start_diag_payment(*, case_id: str, max_user_id: str) -> dict[str, Any] | None:
    """После явного «да»: черновик DIAG → оферта → pay link в MAX."""
    from sfrfr.services.max_bot_invoice import start_diag_payment_after_yes

    return start_diag_payment_after_yes(
        case_id=case_id,
        max_user_id=max_user_id,
        offer_version=OFFER_VERSION,
    )


def handle(
    rec: MaxIntakeRecord,
    reply: Reply,
    *,
    payload: str,
    case_id: str | None,
    max_user_id: str,
    log_event: Callable[[str], Any],
) -> tuple[str, str] | None:
    """Кнопки diag:*. None — не наш апдейт."""
    pl = str(payload or "").strip()
    if not pl.startswith(CALLBACK_PREFIX):
        return None

    if pl == CHECKLIST:
        clear_pending(rec)
        from sfrfr.integrations.max import checklist_offer

        reply(checklist_offer.OFFER_TEXT, checklist_offer.offer_keyboard())
        log_event("Выбор после анкеты: пока чек-лист")
        return "diag_checklist", checklist_offer.OFFER_TEXT

    if pl != YES:
        return None

    clear_pending(rec)
    if not case_id:
        reply(NO_CASE_TEXT, None)
        return "diag_yes_no_case", NO_CASE_TEXT

    result = start_diag_payment(case_id=case_id, max_user_id=max_user_id)
    if not result or not result.get("ok"):
        reason = (result or {}).get("reason")
        if reason == "consent":
            reply(CONSENT_NEEDED_TEXT, None)
            return "diag_yes_consent", CONSENT_NEEDED_TEXT
        reply(FAIL_TEXT, None)
        return "diag_yes_fail", FAIL_TEXT

    if result.get("already_paid"):
        text = (
            "Диагностика уже оплачена. Пришлите документы прямо в этот чат — "
            "PDF или фото. Вопросы по делу пишите здесь."
        )
        reply(text, None)
        log_event("Выбор после анкеты: диагностика уже оплачена")
        return "diag_yes_paid", text

    reply(CONFIRM_TEXT, None)
    log_event("Выбор после анкеты: оформить диагностику 3 000 ₽")
    return "diag_yes", CONFIRM_TEXT
