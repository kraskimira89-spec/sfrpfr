"""Подготовка MAX-уведомления по результату первичной проверки.

Только enqueue через case_chat_outbox. Live-отправка — у worker.
dedupe: message_id = precheck:{check_id}.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ACTION_HINT = "primary_doc_precheck_notify"


def build_precheck_max_message(primary: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Текст + inline buttons по outcome (не все сразу)."""
    outcome = str(primary.get("outcome") or "")
    summary = str(primary.get("client_summary") or "").strip()
    rec = primary.get("recommendation") if isinstance(primary.get("recommendation"), dict) else {}
    text = summary or "Первичная проверка документов завершена."
    buttons: list[dict[str, str]] = [
        {"text": "Посмотреть резюме", "payload": "precheck:summary"},
    ]
    if outcome == "discrepancies_found":
        buttons.append(
            {"text": "Что означает расхождение?", "payload": "precheck:explain"}
        )
        if rec.get("offer_paid_analysis"):
            buttons.append(
                {
                    "text": "Что входит в подробный анализ?",
                    "payload": "precheck:offer_info",
                }
            )
            buttons.append(
                {"text": "Заказать подробный анализ", "payload": "precheck:order"}
            )
        buttons.append({"text": "Пока не нужно", "payload": "precheck:decline"})
    elif outcome in {"insufficient_documents", "needs_clarification"}:
        buttons.append(
            {"text": "Какие документы нужны?", "payload": "precheck:need_docs"}
        )
        buttons.append(
            {"text": "Задать вопрос сотруднику", "payload": "precheck:ask_staff"}
        )
    else:
        buttons.append(
            {"text": "Задать вопрос сотруднику", "payload": "precheck:ask_staff"}
        )
    rows = [
        [{"type": "callback", "text": b["text"], "payload": b["payload"]}] for b in buttons
    ]
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": rows}}]
    return text, attachments


def enqueue_precheck_client_notify(
    *,
    case_id: str,
    check_id: str,
    primary: dict[str, Any],
    max_user_id: str | None,
) -> dict[str, Any]:
    """Поставить уведомление в outbox. Без MAX — явный skip для staff UI."""
    if not max_user_id:
        return {
            "ok": False,
            "skipped": True,
            "reason": "no_max_user",
            "message": "Результат сохранён в кабинете; MAX не привязан.",
        }
    text, attachments = build_precheck_max_message(primary)
    message_id = f"precheck:{check_id}"
    try:
        from sfrfr.services.case_chat_delivery import enqueue_max_delivery

        ok = enqueue_max_delivery(
            case_id=case_id,
            message_id=message_id,
            max_user_id=str(max_user_id),
            body=text,
            attachments=attachments,
        )
        return {
            "ok": bool(ok),
            "skipped": False,
            "message_id": message_id,
            "hint": ACTION_HINT,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("precheck notify enqueue failed: %s", type(exc).__name__)
        return {"ok": False, "skipped": False, "reason": type(exc).__name__}
