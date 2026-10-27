"""Входящая почта с вложениями → дело по opaque-токену или очередь «Требует привязки»."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.services.extra_document_intake import (
    MailInboundProcessedStore,
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
    processed_store: MailInboundProcessedStore | None = None,
) -> dict[str, Any]:
    """Обработать одно письмо.

    attachments: (filename, bytes, content_type).
    Без токена — в unbound queue с сохранением байтов, без авто-привязки по ФИО/email.
    Письмо считается обработанным только после save в дело или успешной постановки в очередь.
    """
    processed = processed_store or MailInboundProcessedStore()
    mid = (message_id or "").strip()
    if mid and processed.is_processed(mid):
        return {
            "ok": True,
            "deduped": True,
            "status": "already_processed",
            "message_id": mid,
        }

    case_id = bind_case_from_mail_subject(
        subject,
        secret=secret,
        known_case_ids=known_case_ids,
        sender=sender,
    )
    names = [n for n, _, _ in attachments]
    if not case_id:
        # Не надёжно сохранили вложения → не помечаем processed (повторный опрос).
        try:
            row = UnboundMailQueue().enqueue(
                message_id=message_id,
                subject=subject,
                sender=sender,
                attachment_names=names,
                attachments=attachments,
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("unbound enqueue failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "bound": False,
                "status": "enqueue_failed",
                "error": type(exc).__name__,
                "honest": True,
            }
        if row.get("deduped"):
            processed.mark_processed(mid, status="needs_binding_deduped")
            return {
                "ok": True,
                "bound": False,
                "status": "needs_binding",
                "queue_item": row,
                "deduped": True,
                "honest": True,
            }
        blobs_saved = int(row.get("blobs_saved") or 0)
        expected = sum(1 for _, data, _ in attachments if data)
        if expected and blobs_saved < expected:
            return {
                "ok": False,
                "bound": False,
                "status": "blobs_incomplete",
                "queue_item": row,
                "honest": True,
                "detail": "Вложения не полностью сохранены — повтор при следующем опросе.",
            }
        processed.mark_processed(mid, status="needs_binding")
        return {
            "ok": True,
            "bound": False,
            "status": "needs_binding",
            "queue_item": row,
            "honest": True,
            "detail": "Нет opaque-токена SFRFR-DOC — письмо не добавлено в дело автоматически.",
        }

    if not attachments:
        processed.mark_processed(mid, status="no_attachments")
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
                upload_source="email",
            )
            try:
                repo.audit(case_id, None, f"extra_document_email:{doc_id[:8]}")
            except Exception:  # noqa: BLE001
                pass
        saved.append({"filename": filename, "ok": True, "document_id": doc_id})

    ok_count = sum(1 for s in saved if s.get("ok"))
    expected = sum(1 for _, data, _ in attachments if data)
    if expected and ok_count < expected:
        return {
            "ok": False,
            "bound": True,
            "case_id": case_id,
            "status": "partial_save",
            "saved": saved,
            "preserves_funnel": True,
            "detail": "Не все вложения сохранены — не помечаем письмо обработанным.",
        }

    processed.mark_processed(mid, status="saved")
    return {
        "ok": True,
        "bound": True,
        "case_id": case_id,
        "status": "saved",
        "saved": saved,
        "preserves_funnel": True,
    }
