"""Отказ от следующей оплаты: выбор клиента, не давление (§20.23).

Отказ от нового offer ≠ отказ от текущего заказа / возврат / удаление / stop.
Связь с objection_policy.may_reoffer_after_signal — не дублировать offer.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final

from sfrfr.services.objection_policy import (
    PAYMENT_REFUSAL_IS_NOT,
    ClientSignalKind,
    may_reoffer_after_signal,
)


class RefuseNextVariant(StrEnum):
    REFUSE_NEXT = "refuse_next"  # А
    THINKS_INCLUDED = "thinks_included"  # Б
    NO_MONEY = "no_money"  # В
    SELF_CONTINUE = "self_continue"  # Г
    WAIT_PRIOR = "wait_prior"  # Д
    WANT_FREE_NEXT = "want_free_next"  # Е
    FEAR_DELETE = "fear_delete"  # Ж
    URGENT_NO_BUY = "urgent_no_buy"  # З
    RETURNS_LATER = "returns_later"  # И


class RefusalEvent(StrEnum):
    REFUSE_OFFER = "refuse_offer"
    PAUSE_DECISION = "pause_decision"
    REFUSE_FURTHER_PAID = "refuse_further_paid"
    STOP_CURRENT_SERVICE = "stop_current_service"
    REFUND_REQUEST = "refund_request"
    STOP_OPTIONAL_MESSAGES = "stop_optional_messages"
    DELETE_DATA = "delete_data"
    CLIENT_REINITIATES = "client_reinitiates"


_RETURNS_LATER_RE: Final = re.compile(
    r"передумал.{0,30}продолж|"
    r"что\s+нужно.{0,20}продолж|"
    r"хочу\s+вс[её]\s+же\s+продолж",
    re.I | re.DOTALL,
)
_FEAR_DELETE_RE: Final = re.compile(
    r"удалите?\s+мои\s+документ|"
    r"если\s+не\s+заплач.{0,30}удал|"
    r"документы\s+удал",
    re.I | re.DOTALL,
)
_WANT_FREE_RE: Final = re.compile(
    r"больше\s+не\s+плачу.{0,40}обязан|"
    r"бесплатно.{0,20}жалоб|"
    r"не\s+плачу.{0,30}напишете\s+жалоб",
    re.I | re.DOTALL,
)
_WAIT_PRIOR_RE: Final = re.compile(
    r"сначала\s+сделайте\s+то.{0,30}заплатил|"
    r"за\s+что\s+я\s+уже\s+заплатил|"
    r"потом\s+поговорим",
    re.I | re.DOTALL,
)
_SELF_RE: Final = re.compile(
    r"дальше\s+я\s+сам|"
    r"сам\s+пойду\s+в\s+сфр|"
    r"ваши\s+услуги\s+больше\s+не\s+нужны",
    re.I,
)
_INCLUDED_RE: Final = re.compile(
    r"почему\s+снова\s+платить|"
    r"вс[её]\s+входит|"
    r"говорили.{0,20}входит",
    re.I | re.DOTALL,
)
_URGENT_NO_BUY_RE: Final = re.compile(
    r"денег\s+на\s+жалобу\s+нет|"
    r"значит\s+ничего\s+делать\s+не\s+буду",
    re.I,
)
_NO_MONEY_RE: Final = re.compile(
    r"денег\s+больше\s+нет|"
    r"хотел\s+бы\s+продолжить.{0,20}денег|"
    r"нет\s+денег",
    re.I | re.DOTALL,
)
_REFUSE_NEXT_RE: Final = re.compile(
    r"больше\s+ни\s+рубля|"
    r"больше\s+платить\s+не\s+буду|"
    r"уже\s+заплатил.{0,30}больше|"
    r"следующ(ий|ую)\s+этап.{0,20}не\s+(нужен|буду)",
    re.I | re.DOTALL,
)

BANNED_REFUSE_REPLY: Final[tuple[str, ...]] = (
    "оформите кредит",
    "займите",
    "потеряете пенсию",
    "документы удалим если не оплатите",
    "успейте сегодня",
    "дело успешно завершено",
    "заказ оформлен",
    "исправление за доплату",
)


def classify_refuse_next_signal(text: str) -> RefuseNextVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _RETURNS_LATER_RE.search(raw):
        return RefuseNextVariant.RETURNS_LATER
    if _FEAR_DELETE_RE.search(raw):
        return RefuseNextVariant.FEAR_DELETE
    if _WANT_FREE_RE.search(raw):
        return RefuseNextVariant.WANT_FREE_NEXT
    if _WAIT_PRIOR_RE.search(raw):
        return RefuseNextVariant.WAIT_PRIOR
    if _SELF_RE.search(raw):
        return RefuseNextVariant.SELF_CONTINUE
    if _INCLUDED_RE.search(raw):
        return RefuseNextVariant.THINKS_INCLUDED
    if _URGENT_NO_BUY_RE.search(raw):
        return RefuseNextVariant.URGENT_NO_BUY
    if _NO_MONEY_RE.search(raw):
        return RefuseNextVariant.NO_MONEY
    if _REFUSE_NEXT_RE.search(raw):
        return RefuseNextVariant.REFUSE_NEXT
    return None


def map_refusal_event(variant: RefuseNextVariant) -> RefusalEvent:
    if variant == RefuseNextVariant.RETURNS_LATER:
        return RefusalEvent.CLIENT_REINITIATES
    if variant == RefuseNextVariant.FEAR_DELETE:
        return RefusalEvent.REFUSE_FURTHER_PAID
    if variant in {
        RefuseNextVariant.REFUSE_NEXT,
        RefuseNextVariant.NO_MONEY,
        RefuseNextVariant.SELF_CONTINUE,
        RefuseNextVariant.URGENT_NO_BUY,
        RefuseNextVariant.WANT_FREE_NEXT,
    }:
        return RefusalEvent.REFUSE_FURTHER_PAID
    if variant == RefuseNextVariant.WAIT_PRIOR:
        return RefusalEvent.PAUSE_DECISION
    if variant == RefuseNextVariant.THINKS_INCLUDED:
        return RefusalEvent.PAUSE_DECISION
    return RefusalEvent.REFUSE_OFFER


def may_reoffer_after_refuse_next(variant: RefuseNextVariant) -> bool:
    """Повтор того же offer без нового основания — запрещён."""
    if variant == RefuseNextVariant.RETURNS_LATER:
        return False  # можно обсудить, но не авто-заказ; offer только после согласия
    return False


def may_stop_paid_work_on_refuse_next() -> bool:
    return False


def may_treat_refuse_as_refund() -> bool:
    return False


def may_treat_refuse_as_delete_data() -> bool:
    return False


def may_treat_refuse_as_stop_all_messages() -> bool:
    return False


def may_block_paid_deliverables_for_new_offer() -> bool:
    return False


def may_sell_fix_of_own_defect() -> bool:
    return False


def may_pressure_with_doc_deletion() -> bool:
    return False


def may_cross_channel_reoffer_after_refuse() -> bool:
    return False


def may_auto_create_order_on_return() -> bool:
    return False


def may_call_service_end_pension_success() -> bool:
    return False


def refusal_is_not_bundle() -> frozenset[str]:
    """Не сливать отказ от оплаты с удалением/stop/«проблем нет»."""
    return PAYMENT_REFUSAL_IS_NOT


def align_with_objection_signal(variant: RefuseNextVariant) -> ClientSignalKind:
    if variant == RefuseNextVariant.NO_MONEY:
        return ClientSignalKind.NO_MONEY
    if variant in {
        RefuseNextVariant.REFUSE_NEXT,
        RefuseNextVariant.SELF_CONTINUE,
        RefuseNextVariant.WANT_FREE_NEXT,
    }:
        return ClientSignalKind.HARD_REFUSE
    if variant == RefuseNextVariant.WAIT_PRIOR:
        return ClientSignalKind.CLAIM
    if variant == RefuseNextVariant.THINKS_INCLUDED:
        return ClientSignalKind.CLAIM
    return ClientSignalKind.HARD_REFUSE


def offer_gate_after_refuse(variant: RefuseNextVariant) -> dict[str, Any]:
    kind = align_with_objection_signal(variant)
    return {
        "may_reoffer": may_reoffer_after_refuse_next(variant)
        and may_reoffer_after_signal(kind),
        "stop_unagreed_next_stage": True,
        "continue_paid_obligations": True,
        "event": map_refusal_event(variant).value,
        "not": sorted(refusal_is_not_bundle()),
    }


def client_closure_summary(
    *,
    checked: str,
    delivered: str,
    preliminary: str = "",
    still_in_order: str = "",
    not_done: str = "",
    next_step: str = "",
    deadline: str | None = None,
    how_get_materials: str = "",
) -> dict[str, Any]:
    """Итог §39 — не «пенсионный успех»."""
    return {
        "checked": checked,
        "delivered": delivered,
        "preliminary": preliminary,
        "still_in_order": still_in_order,
        "not_done": not_done,
        "next_step": next_step,
        "deadline": deadline,
        "how_get_materials": how_get_materials,
        "service_end_is_not_pension_success": True,
    }


def reply_has_banned_refuse_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_REFUSE_REPLY)
