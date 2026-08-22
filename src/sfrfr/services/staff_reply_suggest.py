"""Подсказки ответов сотруднику: DeepSeek в Yandex AI Studio, без ПДн."""

from __future__ import annotations

import re
from typing import Any

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.core.copy import POSITION_SHORT

SYSTEM = f"""Ты помощник сотрудника сервиса «Проверка стажа».

{POSITION_SHORT}

Сгенерируй 3 коротких варианта ответа клиенту в MAX (без ПДн, без обещаний перерасчёта).
Формат строго:
1) ...
2) ...
3) ...
Каждый вариант — 1–2 предложения на русском.
"""


def suggest_staff_replies(
    *,
    messages: list[dict[str, Any]],
    pipeline_status: str | None = None,
    b2c_status: str | None = None,
) -> list[str]:
    llm = LLMClient.for_analyze(allow_fallback=False)
    if not llm.available:
        return []

    lines: list[str] = []
    for row in messages[-12:]:
        kind = str(row.get("author_kind") or "unknown")
        body = redact_for_llm(str(row.get("body") or ""))[:400]
        if not body:
            continue
        lines.append(f"{kind}: {body}")
    if not lines:
        lines.append("(история пуста — предложи вежливое первое сообщение)")

    user = (
        f"Этап дела: pipeline={pipeline_status or '—'}, b2c={b2c_status or '—'}\n"
        f"Лента (обезличено):\n" + "\n".join(lines)
    )
    try:
        raw = llm.chat(system=SYSTEM, user=user, temperature=0.4)
    except Exception:  # noqa: BLE001
        return []

    out: list[str] = []
    for m in re.finditer(r"^\s*\d+[).]\s*(.+)$", raw or "", re.M):
        text = m.group(1).strip().strip("«»\"'")
        if text:
            out.append(text[:400])
        if len(out) >= 3:
            break
    if not out and (raw or "").strip():
        # fallback: split by newlines
        for line in (raw or "").splitlines():
            t = line.strip().lstrip("1234567890). ").strip()
            if len(t) > 12:
                out.append(t[:400])
            if len(out) >= 3:
                break
    return out
