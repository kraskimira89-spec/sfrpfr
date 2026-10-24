"""Несколько смыслов в одной реплике — не взаимоисключающие ярлыки.

Порядок приоритетов и разбор направлений (§ консолидация SFRFR-110).
Не создаёт новую БД-схему.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final

from sfrfr.services.anxiety_dialogue_policy import (
    AnxietyVariant,
    classify_anxiety_signal,
    is_ordinary_worry_not_emergency,
)
from sfrfr.services.calculation_explain_policy import classify_calculation_distrust
from sfrfr.services.complaint_aggression_policy import (
    classify_complaint_signal,
    extract_message_layers,
)
from sfrfr.services.contradiction_policy import classify_contradiction_signal
from sfrfr.services.expectation_alignment_policy import classify_expectation_signal
from sfrfr.services.lost_document_policy import classify_lost_document_signal
from sfrfr.services.price_refuse_policy import classify_price_refuse_signal
from sfrfr.services.refuse_next_stage_policy import (
    classify_refuse_next_signal,
    may_reoffer_after_refuse_next,
)


class IntentDomain(StrEnum):
    SAFETY = "safety"
    ACCESS = "access"
    COMMUNICATIONS = "communications"
    CLAIM = "claim"
    DEADLINE = "deadline"
    SUBSTANCE = "substance"
    COMMERCIAL = "commercial"
    FORM = "form"


PRIORITY_ORDER: Final[tuple[IntentDomain, ...]] = (
    IntentDomain.SAFETY,
    IntentDomain.ACCESS,
    IntentDomain.COMMUNICATIONS,
    IntentDomain.CLAIM,
    IntentDomain.DEADLINE,
    IntentDomain.SUBSTANCE,
    IntentDomain.COMMERCIAL,
)

CLAIM_LIFECYCLE: Final[tuple[str, ...]] = (
    "message_received",
    "request_saved",
    "internal_task_created",
    "claim_registered",
    "assignee_set",
    "decision_made",
    "action_done",
)

_RELATIVE_ACCESS_RE: Final = re.compile(
    r"за\s+(мужа|жену|маму|папу|мать|отца|родственник)|"
    r"это\s+не\s+мо[её]\s+дело|чужое\s+дело",
    re.I,
)
_STOP_COMMS_RE: Final = re.compile(
    r"не\s+пишите|больше\s+ничего\s+не\s+предлага|"
    r"отписаться|/stop|стоп$",
    re.I,
)
_DEADLINE_FACT_RE: Final = re.compile(
    r"срок|до\s+\d{1,2}[./]\d{1,2}|завтра\s+уже",
    re.I,
)


def claim_status_may_announce(status: str) -> bool:
    """«Претензия принята» только на claim_registered+."""
    try:
        idx = CLAIM_LIFECYCLE.index(status)
    except ValueError:
        return False
    return idx >= CLAIM_LIFECYCLE.index("claim_registered")


def intention_vs_result_phrases() -> dict[str, str]:
    return {
        "intention": "Попробую зарегистрировать запрос.",
        "success_prefix": "Запрос зарегистрирован:",
        "failure": "Зарегистрировать запрос не удалось.",
    }


def substantial_change_does_not_lift_offer_refuse() -> bool:
    """§17.5 консолидация: смена обстоятельств ≠ авто-сброс отказа."""
    return True


def parse_multi_intent(text: str) -> dict[str, Any]:
    """Независимые направления в одной реплике."""
    raw = (text or "").strip()
    domains: dict[str, Any] = {
        "form": None,
        "substance": [],
        "commercial": None,
        "claim": None,
        "communications": None,
        "access": None,
        "safety": None,
        "deadline_mentioned": bool(_DEADLINE_FACT_RE.search(raw)),
        "layers": extract_message_layers(raw) if raw else {},
        "priority": [d.value for d in PRIORITY_ORDER],
        "mutually_exclusive": False,
    }
    if not raw:
        return domains

    anx = classify_anxiety_signal(raw)
    if anx == AnxietyVariant.IMMEDIATE_DANGER:
        domains["safety"] = anx.value
    elif anx is not None:
        domains["form"] = anx.value
    elif is_ordinary_worry_not_emergency(raw):
        domains["form"] = "ordinary_worry"

    if _RELATIVE_ACCESS_RE.search(raw):
        domains["access"] = "relative_or_foreign_case"

    if _STOP_COMMS_RE.search(raw):
        domains["communications"] = "stop_or_no_offers"

    complaint = classify_complaint_signal(raw)
    if complaint is not None:
        domains["claim"] = complaint.value
    else:
        reqs = (domains.get("layers") or {}).get("requirements") or []
        if any(
            r in reqs
            for r in ("review_complaint", "refund", "formal_claim", "delete_data")
        ):
            domains["claim"] = "requirement_detected"
        elif re.search(r"жалоб|пожалова|претензи|возврат", raw, re.I):
            domains["claim"] = "requirement_detected"

    price = classify_price_refuse_signal(raw)
    refuse = classify_refuse_next_signal(raw)
    if price is not None:
        domains["commercial"] = {
            "kind": "price_refuse",
            "variant": price.value,
            "may_reoffer": False,
        }
    elif refuse is not None:
        domains["commercial"] = {
            "kind": "refuse_next",
            "variant": refuse.value,
            "may_reoffer": may_reoffer_after_refuse_next(refuse),
        }

    for label, fn in (
        ("calc", classify_calculation_distrust),
        ("contradiction", classify_contradiction_signal),
        ("lost_doc", classify_lost_document_signal),
        ("expectation", classify_expectation_signal),
    ):
        got = fn(raw)
        if got is not None:
            domains["substance"].append({"kind": label, "variant": got.value})
    low = raw.casefold()
    if not any(s["kind"] == "calc" for s in domains["substance"]):
        if "не верю" in low and ("расчёт" in low or "расчет" in low or "сумм" in low):
            domains["substance"].append(
                {"kind": "calc", "variant": "ask_source"}
            )

    return domains


def response_plan_from_intents(parsed: dict[str, Any]) -> dict[str, Any]:
    """Что нельзя потерять в ответе / действиях."""
    must: list[str] = []
    forbid_offer = False
    if parsed.get("safety"):
        must.append("safety_pause")
        forbid_offer = True
    if parsed.get("access"):
        must.append("access_check")
        forbid_offer = True
    if parsed.get("communications"):
        must.append("apply_comms_scope")
        forbid_offer = True
    if parsed.get("claim"):
        must.append("preserve_claim_requirements")
        forbid_offer = True
    if parsed.get("commercial"):
        must.append("accept_refuse_next")
        forbid_offer = True
    if parsed.get("form"):
        must.append("gentle_short_form")
    for s in parsed.get("substance") or []:
        must.append(f"handle_{s['kind']}")
    if parsed.get("deadline_mentioned"):
        must.append("deadline_neutral_if_confirmed")
    return {
        "must_cover": must,
        "may_reoffer": False if forbid_offer else None,
        "announce_claim_accepted_without_registration": False,
        "mutually_exclusive_label": False,
    }
