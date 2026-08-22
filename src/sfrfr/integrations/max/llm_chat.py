"""ТЗ-26: ограниченный LLM-ответ в личном чате MAX через DeepSeek (Yandex AI Studio)."""

from __future__ import annotations

import logging
import re
from typing import Any

from sfrfr.ai.guardrails import redact_for_llm
from sfrfr.ai.llm import LLMClient
from sfrfr.core.config import get_settings
from sfrfr.core.copy import POSITION_SHORT
from sfrfr.integrations.max.intake import free_text_nudge

logger = logging.getLogger(__name__)

_PDN_HINT = re.compile(
    r"(снилс|паспорт|\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b|\b\d{11,}\b)",
    re.IGNORECASE,
)

CLIENT_CHAT_SYSTEM = f"""Ты бот сервиса «Проверка стажа» в MAX.

{POSITION_SHORT}

Правила:
- Короткий ответ на русском (до 500 символов).
- Не обещай перерасчёт, суммы пенсии, ЕДВ, «мы подадим в СФР».
- Не проси присылать СНИЛС, паспорт, сканы в чат — только кабинет.
- В конце одной фразой предложи выбрать кнопку ниже или позвать специалиста.
- Не выдумывай юридические выводы по делу.

Формат ответа строго:
REPLY: <текст клиенту>
BUTTONS: <2-4 коротких варианта через | >
"""


def llm_chat_enabled() -> bool:
    return bool(get_settings().max_llm_chat_enabled)


def looks_like_pdn(text: str) -> bool:
    return bool(_PDN_HINT.search(text or ""))


def _parse_llm_payload(raw: str) -> tuple[str, list[str]]:
    text = (raw or "").strip()
    reply = ""
    buttons: list[str] = []
    if "REPLY:" in text.upper() or "BUTTONS:" in text.upper():
        reply_m = re.search(r"REPLY:\s*(.+?)(?:\n\s*BUTTONS:|\Z)", text, re.I | re.S)
        buttons_m = re.search(r"BUTTONS:\s*(.+)$", text, re.I | re.S)
        if reply_m:
            reply = reply_m.group(1).strip()
        if buttons_m:
            buttons = [b.strip() for b in buttons_m.group(1).replace("\n", " ").split("|") if b.strip()]
    else:
        reply = text
    reply = reply[:700].strip()
    buttons = [b[:40] for b in buttons[:4]]
    return reply, buttons


def _soft_buttons(labels: list[str]) -> list[dict[str, Any]]:
    """Доп. кнопки: нажатие приходит как свободный текст (payload soft:…)."""
    from sfrfr.integrations.max.client import inline_buttons_keyboard

    rows: list[list[dict[str, Any]]] = []
    row: list[dict[str, Any]] = []
    for i, label in enumerate(labels):
        row.append({"type": "callback", "text": label, "payload": f"llmsoft:{i}:{label[:32]}"})
        if len(row) >= 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return inline_buttons_keyboard(rows) if rows else []


def reply_to_free_text(
    *,
    user_text: str,
    intake: Any | None,
) -> tuple[str, list[dict[str, Any]], str]:
    """
    Вернуть (text, attachments, action).
    action: max_llm_reply | max_llm_blocked_pdn | max_llm_fallback_nudge
    """
    nudge_text, nudge_kb = free_text_nudge(intake=intake)
    if looks_like_pdn(user_text):
        text = (
            "Пожалуйста, не присылайте СНИЛС, паспорт и сканы в чат. "
            "Загрузите документы в личном кабинете или позовите специалиста кнопкой ниже.\n\n"
            + nudge_text
        )
        return text, nudge_kb, "max_llm_blocked_pdn"

    if not llm_chat_enabled():
        return nudge_text, nudge_kb, "max_llm_fallback_nudge"

    llm = LLMClient.for_analyze(allow_fallback=False)
    if not llm.available:
        logger.warning("max_llm_chat: DeepSeek unavailable model=%s", llm.model)
        return nudge_text, nudge_kb, "max_llm_fallback_nudge"

    step = intake.step() if intake is not None else "whom"
    safe = redact_for_llm(user_text)[:1500]
    user = (
        f"Текущий шаг сценария: {step}\n"
        f"Сообщение клиента (обезличено):\n{safe}\n"
    )
    try:
        raw = llm.chat(system=CLIENT_CHAT_SYSTEM, user=user, temperature=0.3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("max_llm_chat failed: %s", exc)
        return nudge_text, nudge_kb, "max_llm_fallback_nudge"

    reply, soft_labels = _parse_llm_payload(raw)
    if not reply:
        return nudge_text, nudge_kb, "max_llm_fallback_nudge"

    text = f"{reply}\n\nМожно ответить кнопками ниже."
    attachments = list(nudge_kb)
    soft = _soft_buttons(soft_labels)
    if soft and nudge_kb:
        try:
            base_rows = (nudge_kb[0].get("payload") or {}).get("buttons") or []
            soft_rows = (soft[0].get("payload") or {}).get("buttons") or []
            merged = list(base_rows) + list(soft_rows)
            from sfrfr.integrations.max.client import inline_buttons_keyboard

            attachments = inline_buttons_keyboard(merged)
        except Exception:  # noqa: BLE001
            attachments = nudge_kb
    elif soft:
        attachments = soft
    return text, attachments, "max_llm_reply"
