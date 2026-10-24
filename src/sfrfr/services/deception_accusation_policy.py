"""Обвинение в обмане — подтип претензий §20.21, не отдельная ветка (§20.26).

Проверка обещаний / действий / результатов. Без авто-защиты и без юрквалификации.
Доказательства — только обезличенно в тестах/PR.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final

from sfrfr.services.complaint_aggression_policy import (
    ComplaintVariant,
    may_claim_registration_without_success,
    may_discourage_complaint,
    may_offer_upsell_instead_of_claim,
    may_promise_refund_without_authority,
    registration_reply,
)


class DeceptionVariant(StrEnum):
    PROMISED_RECALC = "promised_recalc"  # А
    INVENTED_PROBLEM = "invented_problem"  # Б
    FAKE_CHECK_STATUS = "fake_check_status"  # В
    PAID_NO_WORK = "paid_no_work"  # Г
    HIDDEN_EXTRA_PAY = "hidden_extra_pay"  # Д
    MISSING_CALL_PROMISE = "missing_call_promise"  # Е
    CLAIM_NOT_IN_SCOPE = "claim_not_in_scope"  # Ж
    DEFECT_CONFIRMED = "defect_confirmed"  # З
    DEMAND_FRAUD_LABEL = "demand_fraud_label"  # И


class AccusationFinding(StrEnum):
    DEFECT_CONFIRMED = "defect_confirmed"
    NOT_FOUND_IN_SCOPE = "not_found_in_scope"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


_DEFECT_CONFIRMED_RE: Final = re.compile(
    r"признайте\s+(конкретн(ую|ый)\s+)?(ошибк|дефект)|"
    r"гарантия\s+без\s+основания|"
    r"некорректное\s+сообщение\s+сервиса",
    re.I,
)
_DEMAND_LABEL_RE: Final = re.compile(
    r"напишите\s+прямо.{0,20}мошенник|"
    r"признайте\s+что\s+вы\s+мошенник|"
    r"иначе\s+разговаривать\s+не\s+буду",
    re.I | re.DOTALL,
)
_PROMISED_RECALC_RE: Final = re.compile(
    r"добь[её]тесь\s+перерасч|"
    r"обещали.{0,30}перерасч|"
    r"говорили.{0,30}перерасч.{0,40}обман|"
    r"ничего\s+не\s+гарантируете.{0,20}обман|"
    r"обманули.{0,40}(прибавк|перерасч)|"
    r"обман.{0,40}(прибавк|перерасч)",
    re.I | re.DOTALL,
)
_INVENTED_RE: Final = re.compile(
    r"специально\s+придумали|"
    r"придумали\s+ошибку|"
    r"никакого\s+пропущенного\s+стажа|"
    r"чтобы\s+продать\s+услуг",
    re.I | re.DOTALL,
)
_FAKE_STATUS_RE: Final = re.compile(
    r"проверка\s+ид[её]т.{0,40}не\s+запуска|"
    r"не\s+запускали|"
    r"писали.{0,30}проверка\s+ид[её]т",
    re.I | re.DOTALL,
)
_PAID_NO_WORK_RE: Final = re.compile(
    r"взяли\s+деньги|"
    r"покажите\s+за\s+что\s+я\s+заплатил|"
    r"просто\s+взяли\s+деньги",
    re.I,
)
_HIDDEN_PAY_RE: Final = re.compile(
    r"заманили|"
    r"сначала\s+назвали\s+одну\s+цену|"
    r"требуют\s+ещ[её]|"
    r"скрыли\s+дополнительн",
    re.I,
)
_MISSING_CALL_RE: Final = re.compile(
    r"по\s+телефону|"
    r"сотрудник\s+обещал|"
    r"обещал.{0,20}прибавк",
    re.I | re.DOTALL,
)
_SUBMIT_PROMISE_RE: Final = re.compile(
    r"обещали\s+подать|"
    r"подадите\s+за\s+меня|"
    r"обещали.{0,20}заявлен",
    re.I | re.DOTALL,
)

BANNED_DECEPTION_REPLY: Final[tuple[str, ...]] = (
    "мы такого не говорили",
    "вы неправильно поняли",
    "вы всё придумали",
    "сами виноваты",
    "нам жаль что вы так восприняли",
    "удалите отзыв",
    "откажитесь от жалобы",
    "это просто автоматическое сообщение",
    "мы мошенники",
    "это не мошенничество",
)


def classify_deception_signal(text: str) -> DeceptionVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _DEMAND_LABEL_RE.search(raw):
        return DeceptionVariant.DEMAND_FRAUD_LABEL
    if _DEFECT_CONFIRMED_RE.search(raw):
        return DeceptionVariant.DEFECT_CONFIRMED
    if _PROMISED_RECALC_RE.search(raw):
        return DeceptionVariant.PROMISED_RECALC
    if _INVENTED_RE.search(raw):
        return DeceptionVariant.INVENTED_PROBLEM
    if _FAKE_STATUS_RE.search(raw):
        return DeceptionVariant.FAKE_CHECK_STATUS
    if _HIDDEN_PAY_RE.search(raw):
        return DeceptionVariant.HIDDEN_EXTRA_PAY
    if _MISSING_CALL_RE.search(raw):
        return DeceptionVariant.MISSING_CALL_PROMISE
    if _SUBMIT_PROMISE_RE.search(raw):
        return DeceptionVariant.CLAIM_NOT_IN_SCOPE
    if _PAID_NO_WORK_RE.search(raw):
        return DeceptionVariant.PAID_NO_WORK
    return None


def map_deception_to_complaint(variant: DeceptionVariant) -> ComplaintVariant:
    """Единый процесс 20.21 — без конкурирующей ветки."""
    if variant == DeceptionVariant.PROMISED_RECALC:
        return ComplaintVariant.AI_ERROR_CLAIM
    return ComplaintVariant.FRAUD_ACCUSATION


def may_auto_deny_accusation() -> bool:
    return False


def may_replace_purchase_terms_with_current() -> bool:
    return False


def may_use_disclaimer_to_erase_specific_promise() -> bool:
    return False


def may_invent_new_problem_to_justify_sale() -> bool:
    return False


def may_backdate_check_status_to_fix_history() -> bool:
    return False


def may_treat_missing_record_as_client_lied() -> bool:
    return False


def may_give_legal_fraud_qualification() -> bool:
    return False


def may_close_claim_by_apology_or_text_fix() -> bool:
    return False


def accusation_point_finding(
    *,
    finding: AccusationFinding,
    checked_sources: list[str],
) -> dict[str, Any]:
    return {
        "finding": finding.value,
        "checked_sources": list(checked_sources),
        "client_wrong_label": False,
        "scope_limited": finding == AccusationFinding.NOT_FOUND_IN_SCOPE,
    }


def check_status_timeline_ok(
    *,
    messages_said_running: bool,
    ever_queued: bool,
    ever_running: bool,
) -> dict[str, Any]:
    """Ложный «идёт проверка» при отсутствии запуска — дефект."""
    false_progress = messages_said_running and not (ever_queued or ever_running)
    return {
        "false_progress_message": false_progress,
        "distinguish": ["queued", "running", "done", "delivered"],
        "may_backdate": may_backdate_check_status_to_fix_history(),
    }


def deception_protocol_steps() -> tuple[str, ...]:
    return (
        "receive",
        "extract_claims_and_demands",
        "preserve_messages_and_terms",
        "access_and_order_link",
        "compare_promises_actions_results",
        "finding_per_point",
        "authorized_decision",
        "execute",
        "verifiable_outcome_to_client",
    )


def integration_transition_order() -> tuple[str, ...]:
    """§63.3 — сквозной порядок; аварийный стоп ложных утверждений — отдельно."""
    return (
        "client_message",
        "access_and_context",
        "extract_demands",
        "preserve_source_evidence",
        "register_needed_processes",
        "check_each_disputed_point",
        "finding_per_point",
        "authorized_decision",
        "execute_allowed",
        "verify_result",
        "reply_to_client",
    )


def may_keep_spreading_false_claims_while_investigating() -> bool:
    return False


def claim_registration_must_not_auto() -> tuple[str, ...]:
    """§63.4 — регистрация претензии ≠ авто-эффекты на весь заказ."""
    return (
        "stop_entire_order",
        "cancel_payment",
        "delete_documents",
        "admit_calc_wrong",
        "close_pension_question",
    )


def split_deception_compound(text: str) -> dict[str, Any]:
    """§63.2 — независимые элементы; не один ответ «передали жалобу»."""
    raw = (text or "").strip()
    deception = classify_deception_signal(raw)
    low = raw.casefold()
    elements: list[dict[str, str]] = []
    if deception is not None:
        elements.append(
            {
                "kind": "deception_accusation",
                "variant": deception.value,
                "action": "check_source_message_and_basis",
            }
        )
    if re.search(
        r"больше\s+платить\s+не\s+буду|не\s+буду\s+платить|"
        r"отказываюсь\s+от\s+(оплат|покупк|этап)",
        raw,
        re.I,
    ):
        elements.append(
            {
                "kind": "refuse_new_purchase",
                "action": "preserve_offer_refuse",
            }
        )
    if re.search(r"верните\s+(деньги|оплату)|возврат", raw, re.I):
        elements.append(
            {
                "kind": "refund",
                "action": "register_finance_demand",
            }
        )
    if re.search(
        r"исправьте\s+расч|исправить\s+расч|ошибк[аи].{0,20}расч",
        raw,
        re.I | re.DOTALL,
    ) or ("исправьте" in low and "расчёт" in low):
        elements.append(
            {
                "kind": "fix_calc",
                "action": "check_data_method_dependents",
            }
        )
    return {
        "elements": elements,
        "single_handoff_reply_forbidden": True,
        "accusation_proves_neither_side": True,
        "parent_process": "20.21",
        "competing_claim_branch": False,
    }


def parallel_demands_routes() -> dict[str, str]:
    return {
        "refund": "finance_process",
        "stop_service": "stop_current_order_check",
        "no_offers": "commercial_mute",
        "delete_data": "data_process",
        "want_human": "handoff",
        "publish_review": "do_not_block_continue_substance",
        "calc_error": "reproducible_calc_check",
        "docs_conflict": "source_reconcile",
    }


def deception_offer_gate() -> dict[str, Any]:
    return {
        "parent_process": "20.21",
        "may_reoffer": False,
        "may_discourage_complaint": may_discourage_complaint(),
        "may_announce_registered_without_success": (
            may_claim_registration_without_success()
        ),
        "may_promise_refund": may_promise_refund_without_authority(),
        "may_upsell": may_offer_upsell_instead_of_claim(),
        "registration": registration_reply(succeeded=False),
    }


def reply_has_banned_deception_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_DECEPTION_REPLY)
