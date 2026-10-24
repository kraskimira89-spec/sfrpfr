"""Несогласованные ожидания: цель клиента ≠ гарантия СФР (§20.22).

Согласование с фактами и объёмом услуги без обесценивания цели.
Без ярлыка «завышенные ожидания» и без психологического профиля.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final


class ExpectationVariant(StrEnum):
    GUARANTEED_RAISE = "guaranteed_raise"  # А
    TARGET_AMOUNT = "target_amount"  # Б
    PAYMENT_BUYS_DECISION = "payment_buys_decision"  # В
    SERVICE_SUBMITS = "service_submits"  # Г
    INSTANT_DONE = "instant_done"  # Д
    SCOPE_CREEP = "scope_creep"  # Е
    NEIGHBOR_CASE = "neighbor_case"  # Ж
    APPEAL_AUTO_WIN = "appeal_auto_win"  # З
    ALL_YEARS_WITHOUT_DOCS = "all_years_without_docs"  # И
    ALWAYS_ON_SUPPORT = "always_on_support"  # К
    SERVICE_CREATED_EXPECTATION = "service_created_expectation"  # Л


class StageGate(StrEnum):
    BEFORE_ORDER = "before_order"
    AFTER_PRECHECK = "after_precheck"
    BEFORE_DRAFT = "before_draft"
    BEFORE_SUBMIT = "before_submit"
    AFTER_OFFICIAL = "after_official"
    SCOPE_EXPAND = "scope_expand"


_GUARANTEED_RAISE_RE: Final = re.compile(
    r"пенсия\s+обязательно\s+увелич|"
    r"найд[её]те\s+пропущенн.{0,30}увелич|"
    r"обязательно\s+увелич",
    re.I | re.DOTALL,
)
_TARGET_AMOUNT_RE: Final = re.compile(
    r"плюс\s+\d+|хотя\s+бы\s+\+?\s*\d+|"
    r"расч[её]т\s+под\s+(эту\s+)?сумм|"
    r"сделайте\s+расч[её]т\s+под",
    re.I,
)
_PAYMENT_DECISION_RE: Final = re.compile(
    r"заплатил.{0,40}обязаны\s+добиться|"
    r"заплатил.{0,40}перерасч|"
    r"оплатил.{0,40}обязаны|"
    r"\d+\s+тысяч.{0,40}обязаны",
    re.I | re.DOTALL,
)
_SERVICE_SUBMITS_RE: Final = re.compile(
    r"почему\s+вы\s+ещ[её]\s+не\s+подали|"
    r"не\s+подали\s+заявлен|"
    r"вы\s+подадите\s+за\s+меня|"
    r"документы\s+передал.{0,30}подали",
    re.I | re.DOTALL,
)
_INSTANT_RE: Final = re.compile(
    r"загрузил\s+утром.{0,40}вечером|"
    r"почему\s+вечером\s+ещ[её]\s+нет|"
    r"готового\s+решения|"
    r"уже\s+должно\s+быть\s+готово",
    re.I | re.DOTALL,
)
_SCOPE_RE: Final = re.compile(
    r"льгот|наследств|все\s+выплаты\s+сем|"
    r"оформите\s+ещ[её]|"
    r"занимаетесь\s+пенсиями.{0,40}ещ[её]",
    re.I | re.DOTALL,
)
_NEIGHBOR_RE: Final = re.compile(
    r"соседк|соседу|такой\s+же\s+стаж|"
    r"добавили\s+пять\s+тысяч|"
    r"почему\s+мне\s+нельзя\s+столько",
    re.I,
)
_APPEAL_RE: Final = re.compile(
    r"прокуратур.{0,40}пересчит|"
    r"напишем\s+в\s+прокуратур|"
    r"сразу\s+вс[её]\s+пересчит|"
    r"отказ.{0,30}прокуратур",
    re.I | re.DOTALL,
)
_ALL_YEARS_RE: Final = re.compile(
    r"внесите\s+все\s+двадцать|"
    r"все\s+двадцать.{0,30}документов\s+нет|"
    r"точно\s+работал.{0,40}даже\s+если\s+документов\s+нет",
    re.I | re.DOTALL,
)
_ALWAYS_ON_RE: Final = re.compile(
    r"в\s+любое\s+время|"
    r"круглосуточ|"
    r"специалист\s+должен\s+отвечать|"
    r"оплатил.{0,30}отвечать\s+мне",
    re.I | re.DOTALL,
)
_SERVICE_PROMISE_RE: Final = re.compile(
    r"на\s+сайте\s+написано|"
    r"довед[её]м\s+до\s+результат|"
    r"теперь\s+вы\s+говорите.{0,30}ничего\s+не\s+обеща|"
    r"обещали.{0,30}а\s+теперь",
    re.I | re.DOTALL,
)

BANNED_EXPECTATION_REPLY: Final[tuple[str, ...]] = (
    "завышенные ожидания",
    "гарантируем прибавку",
    "у вас будет не меньше",
    "подадим за вас",
    "скоро будет готово",  # без основания
    "круглосуточно ответим",
    "нереалистичный",
    "хочет невозможного",
    "вы неправильно поняли",
    "обязательно пересчитают",
)

FORBIDDEN_EXPECTATION_LABELS: Final[tuple[str, ...]] = (
    "завышенные ожидания",
    "нереалистичный",
    "хочет невозможного",
    "не понимает объяснений",
)


def classify_expectation_signal(text: str) -> ExpectationVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _SERVICE_PROMISE_RE.search(raw):
        return ExpectationVariant.SERVICE_CREATED_EXPECTATION
    if _ALWAYS_ON_RE.search(raw):
        return ExpectationVariant.ALWAYS_ON_SUPPORT
    if _ALL_YEARS_RE.search(raw):
        return ExpectationVariant.ALL_YEARS_WITHOUT_DOCS
    if _APPEAL_RE.search(raw):
        return ExpectationVariant.APPEAL_AUTO_WIN
    if _NEIGHBOR_RE.search(raw):
        return ExpectationVariant.NEIGHBOR_CASE
    if _SCOPE_RE.search(raw):
        return ExpectationVariant.SCOPE_CREEP
    if _INSTANT_RE.search(raw):
        return ExpectationVariant.INSTANT_DONE
    if _SERVICE_SUBMITS_RE.search(raw):
        return ExpectationVariant.SERVICE_SUBMITS
    if _PAYMENT_DECISION_RE.search(raw):
        return ExpectationVariant.PAYMENT_BUYS_DECISION
    if _TARGET_AMOUNT_RE.search(raw):
        return ExpectationVariant.TARGET_AMOUNT
    if _GUARANTEED_RAISE_RE.search(raw):
        return ExpectationVariant.GUARANTEED_RAISE
    return None


def may_equate_found_period_to_raise() -> bool:
    return False


def may_fit_calculation_to_desired_amount() -> bool:
    return False


def may_treat_payment_as_sfr_guarantee() -> bool:
    return False


def may_claim_service_submits_by_default() -> bool:
    return False


def may_mix_service_sla_with_external() -> bool:
    return False


def may_invent_sla_or_soon() -> bool:
    return False


def may_promise_from_neighbor_case() -> bool:
    return False


def may_add_undocumented_years_to_confirmed() -> bool:
    return False


def may_auto_accept_scope_creep() -> bool:
    return False


def may_blame_client_for_ambiguous_promise() -> bool:
    return False


def may_use_label_inflated_expectations() -> bool:
    return False


def stage_expectation_check(stage: StageGate) -> dict[str, str]:
    """Краткая сверка на переходе этапа (§35), не в каждом сообщении."""
    prompts = {
        StageGate.BEFORE_ORDER: "что входит / результат / чего не гарантируют",
        StageGate.AFTER_PRECHECK: "установлено / требует проверки / не подтверждено",
        StageGate.BEFORE_DRAFT: "предмет / основания / недостающее",
        StageGate.BEFORE_SUBMIT: "кто подаёт / куда / подтверждение",
        StageGate.AFTER_OFFICIAL: "что рассмотрено / что изменилось",
        StageGate.SCOPE_EXPAND: "новый объём / условия / согласие",
    }
    return {
        "stage": stage.value,
        "clarify": prompts[stage],
        "silence_is_not_consent": "true",
        "generic_button_is_not_understanding": "true",
    }


def expectation_case_note(
    *,
    client_goal: str,
    stage_expected: str,
    promised_scope_ref: str = "",
    uncertainties: list[str] | None = None,
    gap: str = "",
    client_choice: str | None = None,
) -> dict[str, Any]:
    """Фиксация без психологических ярлыков (§36)."""
    return {
        "client_goal": client_goal,
        "stage_expected": stage_expected,
        "promised_scope_ref": promised_scope_ref,
        "uncertainties": list(uncertainties or []),
        "gap": gap,
        "explanation": None,
        "client_choice": client_choice,
        "label": None,
        "found_period_is_not_raise": True,
        "payment_is_not_sfr_decision": True,
        "upload_is_not_submit": True,
    }


def reply_has_banned_expectation_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_EXPECTATION_REPLY)


def reply_has_forbidden_expectation_label(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in FORBIDDEN_EXPECTATION_LABELS)
