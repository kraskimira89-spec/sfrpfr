"""Отказ из-за цены — подтип §20.23, не отдельная offer-ветка (§20.25).

Использует offer_gate_after_refuse / may_reoffer_after_refuse_next.
Не профиль «неплатёжеспособный»; причина «цена» — только если клиент назвал.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final

from sfrfr.services.refuse_next_stage_policy import (
    RefuseNextVariant,
    may_auto_create_order_on_return,
    may_block_paid_deliverables_for_new_offer,
    may_call_service_end_pension_success,
    may_cross_channel_reoffer_after_refuse,
    may_reoffer_after_refuse_next,
    may_stop_paid_work_on_refuse_next,
    offer_gate_after_refuse,
)


class PriceRefuseVariant(StrEnum):
    TOO_EXPENSIVE = "too_expensive"  # А
    PRICE_UNJUSTIFIED = "price_unjustified"  # Б
    SURPRISE_EXTRA = "surprise_extra"  # В
    ASK_DISCOUNT = "ask_discount"  # Г
    CHEAPER_ALT = "cheaper_alt"  # Д
    SELF_AFTER_PRICE = "self_after_price"  # Е
    STOP_OFFERS = "stop_offers"  # Ж
    UNFINISHED_PAID = "unfinished_paid"  # З
    DELIVER_RESULT = "deliver_result"  # И
    EXPLAIN_NEXT = "explain_next"  # К
    STOP_FURTHER_ACTION = "stop_further_action"  # Л
    SILENCE_AFTER_DELIVERY = "silence_after_delivery"  # М (системный)
    RETURNS_LATER = "returns_later"  # Н


_SILENCE_MARKER_RE: Final = re.compile(
    r"^\(нет ответа\)$|^\(silence\)$",
    re.I,
)
_RETURNS_LATER_RE: Final = re.compile(
    r"решил\s+продолжить|"
    r"вс[её]\s+ещ[её]\s+можно|"
    r"вернул(ся|ась).{0,20}продолж",
    re.I | re.DOTALL,
)
_DELIVER_RE: Final = re.compile(
    r"отдайте\s+то\s+что\s+уже\s+сделали|"
    r"просто\s+отдайте|"
    r"отдайте\s+результат",
    re.I,
)
_EXPLAIN_NEXT_RE: Final = re.compile(
    r"файлы\s+получил|"
    r"а\s+дальше\s+что|"
    r"получил.{0,20}дальше\s+что",
    re.I | re.DOTALL,
)
_STOP_FURTHER_RE: Final = re.compile(
    r"заниматься\s+этим\s+больше\s+не\s+буду|"
    r"получил.{0,30}больше\s+не\s+буду|"
    r"дальше\s+ничего\s+делать\s+не\s+буду",
    re.I | re.DOTALL,
)
_UNFINISHED_RE: Final = re.compile(
    r"дальше\s+платить\s+не\s+буду.{0,20}законч|"
    r"на\s+этом\s+законч|"
    r"оплаченное\s+доделайте",
    re.I | re.DOTALL,
)
_STOP_OFFERS_RE: Final = re.compile(
    r"дорого.{0,40}больше\s+ничего\s+не\s+предлага|"
    r"больше\s+ничего\s+мне\s+не\s+предлага|"
    r"не\s+предлагайте",
    re.I | re.DOTALL,
)
_ASK_DISCOUNT_RE: Final = re.compile(
    r"сделайте\s+дешевле|"
    r"скидк|"
    r"за\s+такую\s+цену\s+не\s+продолж",
    re.I,
)
_CHEAPER_ALT_RE: Final = re.compile(
    r"есть\s+что[- ]?нибудь\s+дешевле|"
    r"полное\s+сопровождение.{0,20}не\s+потяну|"
    r"вариант\s+подешевле",
    re.I | re.DOTALL,
)
_SURPRISE_RE: Final = re.compile(
    r"если\s+бы\s+я\s+знал.{0,40}доплач|"
    r"потом\s+придётся\s+доплач|"
    r"неожиданн.{0,20}доплат|"
    r"вообще\s+бы\s+не\s+начинал",
    re.I | re.DOTALL,
)
_UNJUSTIFIED_RE: Final = re.compile(
    r"за\s+одно\s+заявлен.{0,20}денег|"
    r"столько\s+денег\?\s*нет|"
    r"нет\s*,?\s*спасибо",
    re.I | re.DOTALL,
)
_SELF_PRICE_RE: Final = re.compile(
    r"дорого.{0,20}буду\s+сам|"
    r"нет\s*,?\s*дорого.{0,20}сам",
    re.I | re.DOTALL,
)
_TOO_EXPENSIVE_RE: Final = re.compile(
    r"слишком\s+дорого|"
    r"для\s+меня\s+это\s+слишком\s+дорого|"
    r"продолжать\s+не\s+буду|"
    r"дорого",
    re.I,
)

BANNED_PRICE_REFUSE_REPLY: Final[tuple[str, ...]] = (
    "оформите кредит",
    "займите",
    "попросите родственников",
    "окупится прибавкой",
    "скидка только сегодня",
    "индивидуальная скидка гарантирована",
    "успейте сегодня",
    "дело успешно завершено",
    "всё было написано",
)


def classify_price_refuse_signal(text: str) -> PriceRefuseVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _SILENCE_MARKER_RE.match(raw):
        return PriceRefuseVariant.SILENCE_AFTER_DELIVERY
    if _RETURNS_LATER_RE.search(raw):
        return PriceRefuseVariant.RETURNS_LATER
    if _STOP_OFFERS_RE.search(raw):
        return PriceRefuseVariant.STOP_OFFERS
    if _DELIVER_RE.search(raw):
        return PriceRefuseVariant.DELIVER_RESULT
    if _EXPLAIN_NEXT_RE.search(raw):
        return PriceRefuseVariant.EXPLAIN_NEXT
    if _STOP_FURTHER_RE.search(raw):
        return PriceRefuseVariant.STOP_FURTHER_ACTION
    if _UNFINISHED_RE.search(raw):
        return PriceRefuseVariant.UNFINISHED_PAID
    if _ASK_DISCOUNT_RE.search(raw):
        return PriceRefuseVariant.ASK_DISCOUNT
    if _CHEAPER_ALT_RE.search(raw):
        return PriceRefuseVariant.CHEAPER_ALT
    if _SURPRISE_RE.search(raw):
        return PriceRefuseVariant.SURPRISE_EXTRA
    if _SELF_PRICE_RE.search(raw):
        return PriceRefuseVariant.SELF_AFTER_PRICE
    if _UNJUSTIFIED_RE.search(raw):
        return PriceRefuseVariant.PRICE_UNJUSTIFIED
    if _TOO_EXPENSIVE_RE.search(raw):
        return PriceRefuseVariant.TOO_EXPENSIVE
    return None


def map_price_to_refuse_next(variant: PriceRefuseVariant) -> RefuseNextVariant:
    """Единый механизм §20.23 — без конкурирующей ветки."""
    if variant in {
        PriceRefuseVariant.SELF_AFTER_PRICE,
        PriceRefuseVariant.STOP_FURTHER_ACTION,
    }:
        return RefuseNextVariant.SELF_CONTINUE
    if variant == PriceRefuseVariant.SURPRISE_EXTRA:
        return RefuseNextVariant.THINKS_INCLUDED
    if variant == PriceRefuseVariant.RETURNS_LATER:
        return RefuseNextVariant.RETURNS_LATER
    if variant == PriceRefuseVariant.UNFINISHED_PAID:
        return RefuseNextVariant.REFUSE_NEXT
    if variant in {
        PriceRefuseVariant.DELIVER_RESULT,
        PriceRefuseVariant.EXPLAIN_NEXT,
        PriceRefuseVariant.SILENCE_AFTER_DELIVERY,
    }:
        return RefuseNextVariant.REFUSE_NEXT
    if variant in {
        PriceRefuseVariant.TOO_EXPENSIVE,
        PriceRefuseVariant.PRICE_UNJUSTIFIED,
        PriceRefuseVariant.ASK_DISCOUNT,
        PriceRefuseVariant.CHEAPER_ALT,
        PriceRefuseVariant.STOP_OFFERS,
    }:
        return RefuseNextVariant.REFUSE_NEXT
    return RefuseNextVariant.REFUSE_NEXT


def price_offer_gate(variant: PriceRefuseVariant) -> dict[str, Any]:
    base = offer_gate_after_refuse(map_price_to_refuse_next(variant))
    base["price_subtype"] = variant.value
    base["reason_price_only_if_client_said"] = True
    base["no_income_profile"] = True
    base["stop_same_stage_offers"] = True
    if variant == PriceRefuseVariant.STOP_OFFERS:
        base["stop_optional_offers"] = True
        base["not_full_message_ban"] = True  # ≠ «вообще не писать»
    if variant == PriceRefuseVariant.CHEAPER_ALT:
        base["may_describe_approved_alt"] = True
        base["may_reoffer"] = False  # описание ≠ обход отказа
    return base


def may_invent_discount() -> bool:
    return False


def may_compare_price_to_unverified_raise() -> bool:
    return False


def may_push_after_clear_price_refuse() -> bool:
    return False


def may_auto_message_on_new_discount_after_stop_offers() -> bool:
    return False


def may_hide_alt_limitations() -> bool:
    return False


def may_require_finance_story() -> bool:
    return False


def price_refuse_state_note(
    *,
    offer: str,
    price_and_terms_version: str,
    client_named_price: bool,
    asked_alt: bool = False,
) -> dict[str, Any]:
    return {
        "offer": offer,
        "price_and_terms_version": price_and_terms_version,
        "decision": "refuse_specific_offer",
        "reason": "price" if client_named_price else None,
        "asked_alt": asked_alt,
        "repeat_offers_forbidden": True,
        "current_order_auto_changed": False,
        "no_income_inference": True,
        "may_reoffer": may_reoffer_after_refuse_next(RefuseNextVariant.REFUSE_NEXT),
        "may_stop_paid": may_stop_paid_work_on_refuse_next(),
        "may_block_deliverables": may_block_paid_deliverables_for_new_offer(),
        "may_cross_channel": may_cross_channel_reoffer_after_refuse(),
        "may_auto_order": may_auto_create_order_on_return(),
        "service_end_is_pension_success": may_call_service_end_pension_success(),
    }


def reply_has_banned_price_refuse_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_PRICE_REFUSE_REPLY)
