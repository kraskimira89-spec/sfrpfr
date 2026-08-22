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
    "Документы клиент загружает только в личном кабинете. "
    "Верни только JSON: "
    '{"next_action":"...","waiting_on":"staff|client|archive|sfr|payment",'
    '"reason":"...","chat_messages":['
    '{"kind":"full","text":"..."},'
    '{"kind":"short","text":"..."},'
    '{"kind":"cabinet_howto","text":"..."}'
    "]} "
    "next_action — одна короткая фраза на русском (до 80 символов). "
    "chat_messages — ровно 3 объекта: full (полный запрос), short (короткое напоминание), "
    "cabinet_howto (как загрузить в кабинет). Без ПДн и обещаний."
)

_KINDS = ("full", "short", "cabinet_howto")


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


def _default_messages(action: str) -> list[dict[str, str]]:
    return [
        {
            "kind": "full",
            "text": (
                f"Здравствуйте! {action}. "
                "Документы загружайте только в личном кабинете — не в этот чат. "
                "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
                "Решение принимает СФР."
            )[:500],
        },
        {
            "kind": "short",
            "text": (
                f"Напоминание: {action}. "
                "Файлы — только в личном кабинете, не в MAX."
            )[:500],
        },
        {
            "kind": "cabinet_howto",
            "text": (
                "Как загрузить: откройте личный кабинет по ссылке из бота или письма → "
                "раздел документов → выберите файл → отправьте. "
                "В этот чат сканы не присылайте."
            )[:500],
        },
    ]


def _normalize_chat_messages(raw: Any, action: str) -> list[dict[str, str]]:
    defaults = _default_messages(action)
    if not isinstance(raw, list) or not raw:
        return defaults
    by_kind: dict[str, str] = {}
    plain: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            kind = str(item.get("kind") or "").strip()
            text = str(item.get("text") or "").strip()
            if kind in _KINDS and text:
                by_kind[kind] = text[:500]
        else:
            text = str(item or "").strip()
            if text:
                plain.append(text[:500])
    out: list[dict[str, str]] = []
    for i, kind in enumerate(_KINDS):
        if kind in by_kind:
            out.append({"kind": kind, "text": by_kind[kind]})
        elif i < len(plain):
            out.append({"kind": kind, "text": plain[i]})
        else:
            out.append(defaults[i])
    return out


def suggest_next_action(case: dict[str, Any]) -> dict[str, Any]:
    waiting = derive_waiting_on(case)
    action = derive_next_action(case, waiting)
    fallback = {
        "next_action": action,
        "waiting_on": waiting,
        "reason": "Эвристика по этапу и чек-листу.",
        "source": "heuristic",
        "chat_messages": _default_messages(action),
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
    action_out = str(data.get("next_action") or "").strip()[:80]
    wait = str(data.get("waiting_on") or waiting).strip()
    if wait not in {"staff", "client", "archive", "sfr", "payment"}:
        wait = waiting
    if not action_out:
        return fallback
    return {
        "next_action": action_out,
        "waiting_on": wait,
        "reason": str(data.get("reason") or "")[:240],
        "source": "deepseek",
        "chat_messages": _normalize_chat_messages(data.get("chat_messages"), action_out),
    }
