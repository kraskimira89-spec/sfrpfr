"""Маппинг свободного текста / soft-кнопок LLM → payload intake FSM."""

from __future__ import annotations

import re
from typing import Any

# Метка кнопки / фраза → payload intake (только известные шаги).
_LABEL_TO_PAYLOAD: dict[str, str] = {
    "за себя": "intake:whom:self",
    "помогаю близкому": "intake:whom:relative",
    "близкому": "intake:whom:relative",
    "для себя": "intake:whom:self",
    "до пенсии": "intake:pension:before",
    "пенсия назначена": "intake:pension:assigned",
    "пенсия уже есть": "intake:pension:assigned",
    "ещё работаю": "intake:pension:before",
    "илс и стаж": "intake:problem:ils_stazh",
    "северный или льготный": "intake:problem:north",
    "север/льгота": "intake:problem:north",
    "документы": "intake:problem:documents",
    "отказ сфр": "intake:problem:sfr_refusal",
    "есть выписка илс": "intake:ils:yes",
    "илс есть": "intake:ils:yes",
    "нужно получить": "intake:ils:need",
    "не знаю, как получить": "intake:ils:unknown",
    "нет": "intake:ils:no",  # неоднозначно — фильтруем по шагу ниже
    "да": "intake:emp:yes",
    "часть документов": "intake:emp:partial",
    "трудовая есть": "intake:emp:yes",
    "с телефона": "intake:device:max",
    "с компьютера": "intake:device:web",
    "нужна помощь": "intake:device:help",
    "уже получил(а) — дальше": "intake:ils_guide:done",
    "уже получил — дальше": "intake:ils_guide:done",
    "уже получила — дальше": "intake:ils_guide:done",
    "продолжить без полного комплекта": "intake:emp_guide:done",
}

# Какой payload допустим на каком шаге FSM
_STEP_ALLOWED: dict[str, frozenset[str]] = {
    "whom": frozenset({"intake:whom:self", "intake:whom:relative"}),
    "pension": frozenset({"intake:pension:before", "intake:pension:assigned"}),
    "problem": frozenset(
        {
            "intake:problem:ils_stazh",
            "intake:problem:north",
            "intake:problem:documents",
            "intake:problem:sfr_refusal",
        }
    ),
    "ils": frozenset(
        {"intake:ils:yes", "intake:ils:need", "intake:ils:no", "intake:ils:unknown"}
    ),
    "ils_howto": frozenset({"intake:ils_guide:done", "intake:ils_guide:mfc"}),
    "employment": frozenset({"intake:emp:yes", "intake:emp:partial", "intake:emp:no"}),
    "emp_howto": frozenset({"intake:emp_guide:done"}),
    "device": frozenset(
        {"intake:device:max", "intake:device:web", "intake:device:help"}
    ),
}

# На шаге ils «нет» / на employment «да» — разные payload при одной метке
_STEP_LABEL_OVERRIDE: dict[tuple[str, str], str] = {
    ("ils", "нет"): "intake:ils:no",
    ("employment", "нет"): "intake:emp:no",
    ("employment", "да"): "intake:emp:yes",
    ("ils", "да"): "intake:ils:yes",
}


def _norm(text: str) -> str:
    t = (text or "").strip().lower().replace("ё", "е")
    t = re.sub(r"\s+", " ", t)
    return t


def resolve_intake_payload(*, label: str, step: str) -> str | None:
    """Вернуть intake:… payload если метка подходит к текущему шагу."""
    key = _norm(label)
    if not key or not step:
        return None
    override = _STEP_LABEL_OVERRIDE.get((step, key))
    if override:
        allowed = _STEP_ALLOWED.get(step) or frozenset()
        return override if override in allowed else None
    payload = _LABEL_TO_PAYLOAD.get(key)
    if not payload:
        # частичное совпадение по началу известных меток
        for cand, pl in _LABEL_TO_PAYLOAD.items():
            if key == cand or key.startswith(cand) or cand in key:
                payload = pl
                break
    if not payload:
        return None
    allowed = _STEP_ALLOWED.get(step) or frozenset()
    if payload not in allowed:
        return None
    return payload


def soft_button_payload(*, label: str, step: str, index: int) -> str:
    """Для LLM BUTTONS: канон шага → intake:, иначе llmsoft:."""
    intake_pl = resolve_intake_payload(label=label, step=step)
    if intake_pl:
        return intake_pl
    safe = (label or "")[:32]
    return f"llmsoft:{index}:{safe}"


def try_resolve_from_user_text(*, user_text: str, intake: Any | None) -> str | None:
    if intake is None:
        return None
    step = intake.step() if hasattr(intake, "step") else "whom"
    return resolve_intake_payload(label=user_text, step=step)
