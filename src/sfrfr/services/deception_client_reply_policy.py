"""§69: текст клиенту при подтверждённой ошибке — только из фактов событий.

Извинение без подтверждённого действия не считается исправлением.
Пустые плейсхолдеры и внутренние статусы в исходящем тексте запрещены.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final


class ConfirmedErrorReplyKind(StrEnum):
    GENERAL = "general"
    PERIOD = "period"
    UNSUPPORTED_AMOUNT = "unsupported_amount"
    FALSE_CHECK_RUNNING = "false_check_running"
    PAYMENT_IMPACT = "payment_impact"
    IMPACT_UNKNOWN = "impact_unknown"
    AFTER_FIX = "after_fix"


_PLACEHOLDER_RE: Final = re.compile(r"\[(?:дата|конкретн|сумма|номер|результат|[^\]]+)\]")

BANNED_IN_CLIENT_REPLY: Final[tuple[str, ...]] = (
    "needs_recheck",
    "verificationstate",
    "claim_registered",
    "outcome",
    "fixing",
    "вы обязаны согласиться",
    "вопрос решён",
    "считайте вопрос закрытым",
)


def may_use_you_were_right_without_confirmation() -> bool:
    return False


def may_say_fixed_before_persist() -> bool:
    return False


def may_say_no_raise_because_amount_was_wrong() -> bool:
    """Ошибка суммы ≠ доказательство отсутствия оснований для перерасчёта."""
    return False


def may_treat_text_fix_as_work_done() -> bool:
    return False


def may_promise_refund_in_error_reply() -> bool:
    return False


def may_require_client_accept_resolved() -> bool:
    return False


def reply_has_empty_placeholders(text: str) -> bool:
    return bool(_PLACEHOLDER_RE.search(text or ""))


def reply_has_banned_internal_labels(text: str) -> bool:
    low = (text or "").casefold()
    return any(b in low for b in BANNED_IN_CLIENT_REPLY)


def build_confirmed_error_reply(
    kind: ConfirmedErrorReplyKind,
    *,
    facts: dict[str, Any],
    client_reported: bool = True,
) -> dict[str, Any]:
    """Собрать ответ только из подтверждённых фактов; иначе отказ от отправки."""
    missing = _required_missing(kind, facts)
    if missing:
        return {
            "ok": False,
            "send": False,
            "missing_facts": missing,
            "text": "",
            "reason": "unconfirmed_or_incomplete_facts",
        }

    text = _render(kind, facts, client_reported=client_reported)
    if reply_has_empty_placeholders(text) or reply_has_banned_internal_labels(text):
        return {
            "ok": False,
            "send": False,
            "missing_facts": ["placeholder_or_internal_label"],
            "text": "",
            "reason": "unsafe_outgoing_text",
        }
    return {
        "ok": True,
        "send": True,
        "missing_facts": [],
        "text": text,
        "kind": kind.value,
        "based_on_intention_only": False,
    }


def _required_missing(
    kind: ConfirmedErrorReplyKind, facts: dict[str, Any]
) -> list[str]:
    base = ["wrong_fact", "confirmed_correction"]
    need = {
        ConfirmedErrorReplyKind.GENERAL: base
        + ["message_date", "what_done_or_limited", "next_step"],
        ConfirmedErrorReplyKind.PERIOD: base + ["date_persist_succeeded"],
        ConfirmedErrorReplyKind.UNSUPPORTED_AMOUNT: ["named_amount"],
        ConfirmedErrorReplyKind.FALSE_CHECK_RUNNING: ["actual_status"],
        ConfirmedErrorReplyKind.PAYMENT_IMPACT: [
            "false_pre_pay_promise",
            "demand_text",
            "demand_registered",
            "registration_ref_or_failure",
        ],
        ConfirmedErrorReplyKind.IMPACT_UNKNOWN: [
            "confirmed_point",
            "provisional_limit_applied",
            "unknown_impact_area",
        ],
        ConfirmedErrorReplyKind.AFTER_FIX: [
            "fixed_list",
            "current_result_place",
            "claim_status_confirmed",
        ],
    }[kind]
    missing: list[str] = []
    for key in need:
        val = facts.get(key)
        if key in (
            "date_persist_succeeded",
            "demand_registered",
            "provisional_limit_applied",
        ):
            if val is None:
                missing.append(key)
            elif key == "provisional_limit_applied" and val is not True:
                missing.append(key)
            continue
        if val is None or val == "":
            missing.append(key)
    return missing


def _render(
    kind: ConfirmedErrorReplyKind,
    facts: dict[str, Any],
    *,
    client_reported: bool,
) -> str:
    if kind == ConfirmedErrorReplyKind.GENERAL:
        open_ = (
            f"Вы были правы, указав на неточность. В нашем сообщении от "
            f"{facts['message_date']} неверно указано {facts['wrong_fact']}. "
            f"Извините, это ошибка с нашей стороны."
            if client_reported
            else (
                f"При проверке мы обнаружили ошибку. В сообщении от "
                f"{facts['message_date']} неверно указано {facts['wrong_fact']}. "
                f"Извините, это ошибка с нашей стороны."
            )
        )
        if not client_reported or not facts.get("message_date"):
            # message_date required when using template with date
            pass
        deadline = ""
        if facts.get("confirmed_deadline"):
            deadline = f" {facts['confirmed_deadline']}"
        return (
            f"{open_}\n\n"
            f"Проверка показала: {facts['confirmed_correction']}.\n\n"
            f"Сейчас {facts['what_done_or_limited']}. "
            f"Ещё нужно проверить {facts.get('known_impact', 'известные последствия')}.\n\n"
            f"Следующий шаг — {facts['next_step']}.{deadline}"
        ).strip()

    if kind == ConfirmedErrorReplyKind.PERIOD:
        if facts.get("date_persist_succeeded") is True:
            return (
                f"В предыдущем ответе мы указали начало работы в "
                f"{facts['wrong_fact']}. По проверенному изображению документа "
                f"читается {facts['confirmed_correction']}. Извините, это наша ошибка.\n\n"
                f"Дата исправлена в деле. Выводы, которые зависели от неё, ещё "
                f"проверяются. Само исправление даты пока не подтверждает изменение "
                f"пенсионного учёта или размера пенсии."
            )
        return (
            f"Ошибка подтверждена: указано {facts['wrong_fact']}, по документу "
            f"читается {facts['confirmed_correction']}. Извините. "
            f"Исправление в деле пока не завершено. Ранее указанную дату "
            f"не следует считать актуальной."
        )

    if kind == ConfirmedErrorReplyKind.UNSUPPORTED_AMOUNT:
        claim_line = ""
        if facts.get("paid_after_message"):
            claim_line = (
                "\n\nЕсли вы уже оформили услугу, ориентируясь на это сообщение, "
                "вопрос нужно рассмотреть отдельно как претензию."
            )
        return (
            f"Ранее мы назвали прибавку {facts['named_amount']}, но достаточного "
            f"основания для этой цифры не было. Извините, такой ответ был некорректным.\n\n"
            f"Эту сумму нельзя считать подтверждённой или использовать для решения "
            f"об оплате. Сейчас проверяются исходные данные и возможность "
            f"обоснованного расчёта.{claim_line}"
        )

    if kind == ConfirmedErrorReplyKind.FALSE_CHECK_RUNNING:
        return (
            "Мы сообщали, что проверка выполняется, хотя подтверждённого запуска "
            "на тот момент не было. Извините: сообщение не соответствовало "
            f"фактическому состоянию.\n\n"
            f"Сейчас проверка {facts['actual_status']}. Отдельно разбираем задержку "
            f"и то, как она повлияла на исполнение вашего заказа."
        )

    if kind == ConfirmedErrorReplyKind.PAYMENT_IMPACT:
        if facts.get("demand_registered") is True:
            return (
                f"Проверка подтвердила, что до оплаты мы сообщили "
                f"{facts['false_pre_pay_promise']}. Извините, это сообщение "
                f"не имело достаточного основания.\n\n"
                f"Ваше требование {facts['demand_text']} зарегистрировано: "
                f"{facts['registration_ref_or_failure']}. Решение по нему пока "
                f"не принято. Исправление ошибки в тексте не заменяет рассмотрение "
                f"вопроса об оплаченной услуге."
            )
        route = facts.get("verified_route") or (
            "Передайте запрос через предусмотренный канал "
            "или дождитесь ответа ответственного."
        )
        return (
            f"Проверка подтвердила, что до оплаты мы сообщили "
            f"{facts['false_pre_pay_promise']}. Извините, это сообщение "
            f"не имело достаточного основания.\n\n"
            f"Зарегистрировать требование сейчас не удалось: "
            f"{facts['registration_ref_or_failure']}. {route} "
            f"Возврат без решения и исполнения обещать не могу."
        )

    if kind == ConfirmedErrorReplyKind.IMPACT_UNKNOWN:
        return (
            f"Ошибка подтверждена в {facts['confirmed_point']}. Пока не установлено, "
            f"повлияла ли она на {facts['unknown_impact_area']}.\n\n"
            f"Поэтому соответствующий результат отмечен как требующий проверки. "
            f"Не буду сообщать, что вопрос полностью исправлен, пока последствия "
            f"не проверены."
        )

    # AFTER_FIX
    open_q = ""
    if facts.get("still_open"):
        open_q = f" Открытым остаётся {facts['still_open']}."
    return (
        f"Проверка последствий завершена. Исправлено: {facts['fixed_list']}. "
        f"Актуальная версия {facts.get('result_label', 'материала')} доступна в "
        f"{facts['current_result_place']}.\n\n"
        f"Прежняя версия отмечена как неактуальная.{open_q}\n\n"
        f"Статус вашего отдельного требования — {facts['claim_status_confirmed']}. "
        f"Если сохранилось конкретное несоответствие — сообщите, разберём."
    )


def general_reply_requires_message_date(facts: dict[str, Any]) -> bool:
    return bool(facts.get("message_date"))
