"""Подсказка следующего шага: DeepSeek V4 Flash в Yandex AI Studio, без ПДн."""

from __future__ import annotations

import json
import re
from typing import Any

from sfrfr.ai.llm import LLMClient
from sfrfr.services.staff_work_queue import derive_next_action, derive_waiting_on

_SYSTEM = (
    "Ты помощник сотрудника сервиса «Проверка стажа». "
    "Мы готовим документы и план, подаёт клиент, решение принимает только СФР. "
    "Не обещай перерасчёт и сумму. Не проси СНИЛС и сканы в чат. "
    "Верни только JSON: "
    '{"next_action":"...","waiting_on":"staff|client|archive|sfr|payment","reason":"..."} '
    "next_action — одна короткая фраза на русском (до 80 символов)."
)


def _anon_case(case: dict[str, Any]) -> dict[str, Any]:
    client = case.get("clients") or {}
    items = [
        {
            "title": str(i.get("title") or "")[:80],
            "owner": i.get("owner"),
            "status": i.get("status"),
            "type": i.get("item_type"),
        }
        for i in (case.get("checklist_items") or [])
        if i.get("status") not in ("done", "cancelled")
    ][:8]
    return {
        "pipeline": case.get("pipeline_status"),
        "b2c": case.get("b2c_status"),
        "waiting_on": derive_waiting_on(case),
        "has_max": bool(client.get("max_user_id")),
        "has_web": bool(client.get("user_id")),
        "open_checklist": items,
        "has_pending_order": any(
            o.get("status") == "pending" for o in (case.get("orders") or [])
        ),
    }


def suggest_next_action(case: dict[str, Any]) -> dict[str, str]:
    waiting = derive_waiting_on(case)
    fallback = {
        "next_action": derive_next_action(case, waiting),
        "waiting_on": waiting,
        "reason": "Эвристика по этапу и чек-листу.",
        "source": "heuristic",
    }
    llm = LLMClient.for_analyze()
    if not llm.available:
        return fallback
    raw = llm.chat(
        system=_SYSTEM,
        user="Обезличенное дело:\n" + json.dumps(_anon_case(case), ensure_ascii=False),
        temperature=0.1,
    )
    match = re.search(r"\{.*\}", raw or "", flags=re.S)
    if not match:
        return fallback
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return fallback
    action = str(data.get("next_action") or "").strip()[:80]
    wait = str(data.get("waiting_on") or waiting).strip()
    if wait not in {"staff", "client", "archive", "sfr", "payment"}:
        wait = waiting
    if not action:
        return fallback
    return {
        "next_action": action,
        "waiting_on": wait,
        "reason": str(data.get("reason") or "")[:240],
        "source": "deepseek",
    }
