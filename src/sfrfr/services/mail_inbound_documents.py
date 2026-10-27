"""Входящая почта с вложениями → дело по opaque-токену или очередь «Требует привязки»."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.services.extra_document_intake import (
    UnboundMailQueue,
    bind_case_from_mail_subject,
    category_to_doc_type,
    notify_extra_document_received,
)

logger = logging.getLogger(__name__)


def process_inbound_mail_message(
    *,
    message_id: str,
    subject: str,
    sender: str,
    attachments: list[tuple[str, bytes, str]],
    known_case_ids: list[str],
    store_document_fn: Any,
    repo: Any,
    secret: str | None = None,
) -> dict[str, Any]:
    """Обработать одно письмо.

    attachments: (filename, bytes, content_type).
    Без токена — в unbound queue, без авто-привязки по ФИО/email.
    """
    case_id = bind_case_from_mail_subject(
        subject,
        secret=secret,
        known_case_ids=known_case_ids,
        sender=sender,
    )
    names = [n for n, _, _ in attachments]
    if not case_id:
        row = UnboundMailQueue().enqueue(
            message_id=message_id,
            subject=subject,
            sender=sender,
            attachment_names=names,
        )
        return {
            "ok": True,
            "bound": False,
            "status": "needs_binding",
            "queue_item": row,
            "honest": True,
            "detail": "Нет opaque-токена SFRFR-DOC — письмо не добавлено в дело автоматически.",
        }

    if not attachments:
        return {
            "ok": True,
            "bound": True,
            "case_id": case_id,
            "status": "no_attachments",
            "saved": [],
        }

    saved: list[dict[str, Any]] = []
    for filename, data, content_type in attachments:
        if not data:
            continue
        try:
            doc = store_document_fn(
                case_id=case_id,
                filename=filename,
                data=data,
                content_type=content_type or "application/octet-stream",
                doc_type=category_to_doc_type("unknown"),
                uploaded_by=None,
                upload_source="email",
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("inbound mail store failed: %s", type(exc).__name__)
            saved.append({"filename": filename, "ok": False, "error": type(exc).__name__})
            continue
        doc_id = str((doc or {}).get("id") or "")
        if doc_id:
            notify_extra_document_received(
                repo=repo,
                case_id=case_id,
                document_id=doc_id,
                doc_type=category_to_doc_type("unknown"),
                actor_id=None,
                may_affect_analysis=True,
            )
            try:
                repo.audit(case_id, None, f"extra_document_email:{doc_id[:8]}")
            except Exception:  # noqa: BLE001
                pass
        saved.append({"filename": filename, "ok": True, "document_id": doc_id})

    return {
        "ok": True,
        "bound": True,
        "case_id": case_id,
        "status": "saved",
        "saved": saved,
        "preserves_funnel": True,
    }
