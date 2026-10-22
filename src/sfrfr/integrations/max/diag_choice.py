"""Выбор диагностики 3 000 ₽: только после краткого разбора и согласия (ТЗ-35)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sfrfr.core.copy import OFFER_URL, PAYMENT_LEGAL_ACCEPTANCE
from sfrfr.integrations.max.client import inline_buttons_keyboard
from sfrfr.integrations.max.intake import MaxIntakeRecord, get_intake_store
from sfrfr.services import brief_analysis as brief
from sfrfr.services.diag_offer_gate import OFFER_TEXT as GATE_OFFER_TEXT
from sfrfr.services.diag_offer_gate import evaluate_diag_offer

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
    "После оплаты продолжим подробный разбор по вашему комплекту в этом чате."
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

NOT_AVAILABLE_TEXT = (
    "Подробную диагностику пока не предлагаем на этом шаге. "
    "Бесплатный чек-лист можно запросить командой /checklist."
)

DETAIL_DECLINED_TEXT = (
    "Хорошо. Если позже понадобится подробный разбор — напишите сюда. "
    "Бесплатный чек-лист: /checklist."
)


def _gated_reply(*, case_id: str | None, reason: str | None = None) -> str:
    """Отказ gate: не подменять причину шаблоном «обрабатываем»."""
    from sfrfr.services.diag_offer_gate import (
        DENY_ANALYSIS_ERROR,
        DENY_NO_ANALYSIS,
        DENY_NO_DISCREPANCY,
        DENY_STALE_ANALYSIS,
    )

    if reason == DENY_NO_DISCREPANCY:
        return (
            "По краткому разбору явных расхождений не видно — "
            "подробную диагностику сейчас не предлагаем. "
            "Бесплатный чек-лист: /checklist."
        )
    if reason in {DENY_NO_ANALYSIS, DENY_STALE_ANALYSIS, DENY_ANALYSIS_ERROR}:
        return (
            "Краткий разбор по комплекту ещё не готов или был сброшен. "
            "Когда итог снова появится в чате — нажмите «Да, подробный разбор». "
            "Чек-лист: /checklist."
        )
    try:
        from sfrfr.services.client_case_status import reply_text, resolve_for_case

        status = resolve_for_case(case_id)
        # receiving/checking — не клеим: это ложный «сейчас обрабатываем» после soft-ask.
        if status.kind == "no_docs":
            return (
                f"{NOT_AVAILABLE_TEXT} "
                "Если документы ещё не в деле — пришлите их в этот чат."
            )
        if status.kind == "missing":
            return f"{NOT_AVAILABLE_TEXT} {reply_text(status)}"
    except Exception:  # noqa: BLE001
        pass
    return f"{NOT_AVAILABLE_TEXT} Бесплатный чек-лист можно запросить командой /checklist."


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
    if (rec.q_answers or {}).get(_STEP_KEY) == "pending":
        return True
    return brief.is_detail_pending(rec)


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


def _evaluate_for_rec(rec: MaxIntakeRecord) -> Any:
    flags = brief.gate_flags_from_intake(rec, reload=True)
    return evaluate_diag_offer(**flags)


def _start_payment_flow(
    rec: MaxIntakeRecord,
    reply: Reply,
    *,
    case_id: str | None,
    max_user_id: str,
    log_event: Callable[[str], Any],
) -> tuple[str, str]:
    clear_pending(rec)
    decision = _evaluate_for_rec(rec)
    if not decision.allowed:
        body = _gated_reply(case_id=case_id, reason=decision.reason)
        reply(body, None)
        log_event(f"Выбор диагностики отклонён gate={decision.reason}")
        return "diag_yes_gated", body

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
        try:
            from sfrfr.services.client_case_status import reply_text, resolve_for_case

            status = resolve_for_case(case_id)
            if status.kind == "no_docs":
                text = (
                    "Диагностика уже оплачена. Пришлите документы прямо в этот чат — "
                    "PDF или фото. Вопросы по делу пишите здесь."
                )
            else:
                text = "Диагностика уже оплачена. " + reply_text(status)
        except Exception:  # noqa: BLE001
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

    if pl == brief.DETAIL_NO:
        brief.mark_detail_consent(rec, wants=False)
        clear_pending(rec)
        reply(DETAIL_DECLINED_TEXT, None)
        log_event("Подробный разбор: отказ клиента")
        return "diag_detail_no", DETAIL_DECLINED_TEXT

    if pl == brief.DETAIL_YES:
        # Heal brief (persist сбрасывает consent). Сам payload = soft-ask
        # уже был в ленте → gaps нельзя откатывать в no_discrepancy.
        brief.ensure_brief_flags_for_offer(rec, case_id=case_id)
        brief.preserve_gaps_after_soft_ask_yes(rec)
        brief.mark_detail_consent(rec, wants=True)
        decision = _evaluate_for_rec(rec)
        if not decision.allowed:
            body = _gated_reply(case_id=case_id, reason=decision.reason)
            reply(body, None)
            log_event(f"Soft-ask да, но gate={decision.reason}")
            return "diag_detail_yes_gated", body
        offer = decision.offer_text or GATE_OFFER_TEXT
        mark_pending(rec)
        reply(offer, offer_keyboard())
        log_event("Soft-ask да → оффер 3 000 ₽")
        return "diag_detail_yes_offer", offer

    if pl != YES:
        return None

    # Старая кнопка: только при полном допуске gate (не обход soft-ask).
    return _start_payment_flow(
        rec,
        reply,
        case_id=case_id,
        max_user_id=max_user_id,
        log_event=log_event,
    )
