"""Подготовка MAX-уведомления по результату первичной проверки.

Только enqueue через case_chat_outbox. Live-отправка — у worker.
dedupe: message_id = precheck:{check_id}.
"""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.services.primary_doc_precheck_max import (
    sanitize_client_text,
    select_max_branch,
)

logger = logging.getLogger(__name__)

ACTION_HINT = "primary_doc_precheck_notify"


def _callback_rows(buttons: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    return [
        [{"type": "callback", "text": b["text"], "payload": b["payload"]}] for b in buttons
    ]


def _payload(sub: str, check_id: str | None) -> str:
    cid = (check_id or "").strip()
    return f"precheck:{sub}:{cid}" if cid else f"precheck:{sub}"


def build_precheck_max_message(
    primary: dict[str, Any],
    *,
    check_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Текст + inline buttons по ветке (не все сразу).

    В payload вшивается check_id, чтобы stale callback сравнивался с актуальной проверкой.
    """
    branch = select_max_branch(primary)
    summary = str(primary.get("client_summary") or "").strip()
    rec = primary.get("recommendation") if isinstance(primary.get("recommendation"), dict) else {}
    text = summary or "Первичная проверка документов завершена."
    cid = (check_id or str(primary.get("check_id") or "")).strip() or None
    pl = lambda sub: _payload(sub, cid)  # noqa: E731
    buttons: list[dict[str, str]] = []

    if branch == "recover":
        text = "Проверка не завершена из‑за технического сбоя. Выводов пока нет."
        buttons = [{"text": "Посмотреть статус", "payload": pl("status")}]
    elif branch == "need_docs":
        buttons = [
            {"text": "Загрузить документы", "payload": pl("upload")},
            {"text": "Какие документы нужны?", "payload": pl("need_docs")},
            {"text": "Задать вопрос сотруднику", "payload": pl("ask_staff")},
        ]
    elif branch == "need_answer":
        buttons = [
            {"text": "Ответить", "payload": pl("answer")},
            {"text": "Задать вопрос сотруднику", "payload": pl("ask_staff")},
        ]
    elif branch == "discrepancy":
        buttons = [
            {"text": "Посмотреть резюме", "payload": pl("summary")},
            {"text": "Что это означает?", "payload": pl("explain")},
        ]
        if rec.get("offer_paid_analysis"):
            buttons.append(
                {
                    "text": "Что входит в подробный анализ?",
                    "payload": pl("offer_info"),
                }
            )
            buttons.append(
                {"text": "Заказать подробный анализ", "payload": pl("order")}
            )
            buttons.append({"text": "Пока не нужно", "payload": pl("decline")})
    elif branch == "clear":
        buttons = [
            {"text": "Посмотреть резюме", "payload": pl("summary")},
            {"text": "Задать вопрос сотруднику", "payload": pl("ask_staff")},
        ]
    else:  # staff
        if str(primary.get("data_status") or "") == "identity_conflict":
            text = (
                "Не удалось надёжно подтвердить, что все документы принадлежат "
                "одному человеку. Передаём сотруднику."
            )
        buttons = [
            {"text": "Обсудить с сотрудником", "payload": pl("ask_staff")},
            {"text": "Посмотреть резюме", "payload": pl("summary")},
        ]

    text, _blocked = sanitize_client_text(text)
    attachments = [{"type": "inline_keyboard", "payload": {"buttons": _callback_rows(buttons)}}]
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
    text, attachments = build_precheck_max_message(primary, check_id=check_id)
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
            "branch": select_max_branch(primary),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("precheck notify enqueue failed: %s", type(exc).__name__)
        return {"ok": False, "skipped": False, "reason": type(exc).__name__}
