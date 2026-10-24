"""Сильная тревога клиента: ясность и один шаг, без диагноза и продажи.

§20.20 / §29 — режим бережного диалога (не медклассификация).
§И — отдельный маршрут непосредственной опасности (не обычное возражение).
Контакты экстренных служб — только из утверждённого справочника; до live — stub.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final


class AnxietyVariant(StrEnum):
    FEAR_LOSE_PENSION = "fear_lose_pension"  # А
    OVERLOAD = "overload"  # Б
    WANT_GUARANTEE = "want_guarantee"  # В
    FEAR_MISS_DEADLINE = "fear_miss_deadline"  # Г
    FEAR_MISTAKE = "fear_mistake"  # Д
    AI_ERROR_SPIKE = "ai_error_spike"  # Е
    WANT_HUMAN_HELP = "want_human_help"  # Ж
    WANT_PAUSE = "want_pause"  # З
    IMMEDIATE_DANGER = "immediate_danger"  # И


class GentleModeFlag(StrEnum):
    SLOW_DOWN = "slow_down"
    SIMPLER = "simpler"
    PAUSE = "pause"
    NEED_HUMAN = "need_human"


_IMMEDIATE_DANGER_RE: Final = re.compile(
    r"причинить\s+себе\s+вред|"
    r"хочу\s+убить\s+себя|покончить\s+с\s+собой|"
    r"суицид|самоубий|"
    r"не\s+могу\s+дышать|"
    r"сейчас\s+себе\s+вред",
    re.I,
)
_FEAR_PENSION_RE: Final = re.compile(
    r"без\s+пенсии\s+остан|"
    r"останусь\s+без\s+пенсии|"
    r"пенси[юя]\s+отмен|"
    r"всю\s+ночь\s+не\s+спал",
    re.I,
)
_OVERLOAD_RE: Final = re.compile(
    r"ничего\s+не\s+понимаю|"
    r"столько\s+всего\s+написали|"
    r"руки\s+трясутся|"
    r"голова\s+идёт\s+кругом",
    re.I,
)
_GUARANTEE_RE: Final = re.compile(
    r"скажите\s+что\s+вс[её]\s+получится|"
    r"вы\s+же\s+уверены|"
    r"гарантируйте|"
    r"значит\s+вс[её]\s+плохо",
    re.I,
)
_DEADLINE_RE: Final = re.compile(
    r"завтра\s+уже\s+будет\s+поздно|"
    r"вс[её]\s+пропущу|"
    r"пропущу\s+срок|"
    r"не\s+успею",
    re.I,
)
_MISTAKE_RE: Final = re.compile(
    r"нажму\s+не\s+туда|"
    r"вс[её]\s+испорчу|"
    r"лучше\s+вообще\s+ничего\s+не\s+буду|"
    r"боюсь\s+ошибиться",
    re.I,
)
_AI_ERROR_RE: Final = re.compile(
    r"вы\s+написали.{0,40}пропал|"
    r"пропало\s+десять\s+лет|"
    r"из[- ]за\s+(вашего|вашей)\s+(сообщен|ошибк)",
    re.I | re.DOTALL,
)
_WANT_HUMAN_RE: Final = re.compile(
    r"одна?\s+не\s+справл|"
    r"поговорил\s+человек|"
    r"можно.{0,20}сотрудник|"
    r"нужен\s+человек",
    re.I,
)
_PAUSE_RE: Final = re.compile(
    r"больше\s+сегодня\s+ничего|"
    r"мне\s+тяжело|"
    r"давайте\s+остановимся|"
    r"хватит\s+на\s+сегодня",
    re.I,
)

# Обычное волнение — не путать с immediate_danger
_ORDINARY_WORRY_RE: Final = re.compile(
    r"очень\s+переживаю|тревож|волнуюсь|страшно|"
    r"нервничаю",
    re.I,
)

BANNED_ANXIETY_REPLY: Final[tuple[str, ...]] = (
    "пенсию точно не отменят",
    "всё получится гарантирую",
    "времени достаточно",
    "это же элементарно",
    "паникёр",
    "нестабильн",
    "трудный клиент",
    "помощь уже вызвана",
    "сотрудник уже подключён",
    "купите доп",
    "оплатите срочно",
)

FORBIDDEN_CLIENT_LABELS: Final[tuple[str, ...]] = (
    "паникёр",
    "нестабильный",
    "трудный",
    "истеричный",
)


def classify_anxiety_signal(text: str) -> AnxietyVariant | None:
    raw = (text or "").strip()
    if not raw:
        return None
    # И — раньше всего; не смешивать с «очень переживаю»
    if _IMMEDIATE_DANGER_RE.search(raw):
        return AnxietyVariant.IMMEDIATE_DANGER
    if _AI_ERROR_RE.search(raw):
        return AnxietyVariant.AI_ERROR_SPIKE
    if _WANT_HUMAN_RE.search(raw):
        return AnxietyVariant.WANT_HUMAN_HELP
    if _PAUSE_RE.search(raw):
        return AnxietyVariant.WANT_PAUSE
    if _DEADLINE_RE.search(raw):
        return AnxietyVariant.FEAR_MISS_DEADLINE
    if _MISTAKE_RE.search(raw):
        return AnxietyVariant.FEAR_MISTAKE
    if _GUARANTEE_RE.search(raw):
        return AnxietyVariant.WANT_GUARANTEE
    if _OVERLOAD_RE.search(raw):
        return AnxietyVariant.OVERLOAD
    if _FEAR_PENSION_RE.search(raw):
        return AnxietyVariant.FEAR_LOSE_PENSION
    return None


def is_ordinary_worry_not_emergency(text: str) -> bool:
    """«Очень переживаю» само по себе ≠ immediate_danger."""
    raw = (text or "").strip()
    if not raw:
        return False
    if _IMMEDIATE_DANGER_RE.search(raw):
        return False
    return bool(_ORDINARY_WORRY_RE.search(raw))


def may_give_false_reassurance() -> bool:
    return False


def may_amplify_worst_case_list() -> bool:
    return False


def may_invent_deadline_date() -> bool:
    return False


def may_create_urgency_for_payment() -> bool:
    return False


def may_offer_upsell_on_anxiety() -> bool:
    return False


def may_diagnose_or_label_client() -> bool:
    return False


def may_claim_emergency_dispatched() -> bool:
    return False


def may_claim_staff_connected_without_registration() -> bool:
    return False


def may_auto_schedule_reminder_without_consent() -> bool:
    return False


def gentle_mode_settings() -> dict[str, Any]:
    """Управляемый режим §29 — не медпрофиль клиента."""
    return {
        "max_sentences": 5,
        "min_sentences": 2,
        "one_action_per_reply": True,
        "one_main_question": True,
        "no_offer_on_anxiety": True,
        "choices": ["continue", "pause", "human"],
        "store_diagnosis": False,
        "allowed_flags": [f.value for f in GentleModeFlag],
    }


def accompaniment_note(
    *,
    flags: list[GentleModeFlag] | None = None,
) -> dict[str, Any]:
    """Только необходимое для сопровождения — без психологических ярлыков."""
    return {
        "flags": [f.value for f in (flags or [])],
        "client_label": None,
        "diagnosis": None,
    }


def verified_emergency_contacts() -> list[dict[str, str]]:
    """Утверждённый справочник. Пусто до согласования live-политики."""
    return []


def immediate_danger_response(*, contacts_approved: bool = False) -> dict[str, Any]:
    """Отдельная политика безопасности — не возражение и не продажа."""
    contacts = verified_emergency_contacts() if contacts_approved else []
    return {
        "pause_case_discussion": True,
        "pause_payment_discussion": True,
        "no_diagnosis": True,
        "no_treatment_advice": True,
        "claim_help_dispatched": False,
        "staff_transfer_is_not_emergency": True,
        "ask_if_immediate_danger": True,
        "contacts": contacts,
        "live_policy_approved": False,
        "template_core": (
            "Мне важно отнестись к вашим словам серьёзно. "
            "Если вы можете причинить себе вред прямо сейчас, "
            "обратитесь в местную экстренную службу и, если возможно, "
            "свяжитесь с человеком, который может побыть рядом. "
            "Вопросы по пенсионному делу сейчас могут подождать. "
            "Вы сейчас в непосредственной опасности?"
        ),
    }


def reply_has_banned_anxiety_rhetoric(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in BANNED_ANXIETY_REPLY)


def reply_has_forbidden_client_label(reply: str) -> bool:
    low = (reply or "").casefold()
    return any(m in low for m in FORBIDDEN_CLIENT_LABELS)


def count_sentences(text: str) -> int:
    parts = re.split(r"[.!?…]+", (text or "").strip())
    return len([p for p in parts if p.strip()])


def reply_fits_gentle_volume(reply: str) -> bool:
    n = count_sentences(reply)
    cfg = gentle_mode_settings()
    return int(cfg["min_sentences"]) <= n <= int(cfg["max_sentences"])
