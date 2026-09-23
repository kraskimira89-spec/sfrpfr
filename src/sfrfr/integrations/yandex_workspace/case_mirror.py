"""Best-effort зеркало документов дела на Яндекс.Диск (SFRFR-cases/{case_id})."""

from __future__ import annotations

import logging
import time
from typing import Any

from sfrfr.integrations.yandex_workspace.disk import (
    mirror_case_document as _mirror,
)
from sfrfr.integrations.yandex_workspace.disk import (
    upload_case_chat_history,
)
from sfrfr.services.document_ingest import SIGNED_DOC_TYPES

logger = logging.getLogger(__name__)

_OUTGOING_DOC_TYPES = SIGNED_DOC_TYPES | {
    "application",
    "draft_application",
    "staff_application",
    "prepared_application",
}

# Не чаще раза в 15 минут на дело (снимок chat/history.md).
_CHAT_EXPORT_MIN_INTERVAL_SEC = 900
_last_chat_export_at: dict[str, float] = {}


def resolve_case_mirror_subfolder(doc_type: str | None) -> str:
    """incoming = сканы клиента; outgoing = заявления / подписанные комплекты."""
    dtype = str(doc_type or "").strip().lower()
    if dtype in _OUTGOING_DOC_TYPES:
        return "outgoing"
    return "incoming"


def mirror_case_document_safe(
    case_id: str,
    filename: str,
    data: bytes,
    *,
    doc_type: str | None = None,
    subfolder: str | None = None,
) -> dict[str, Any]:
    """Не бросает наружу: skipped / ok / error в dict + warning в лог при сбое."""
    dtype = str(doc_type or "").strip().lower()
    if dtype in {"bank_statement", "bank"}:
        return {"ok": False, "skipped": True, "reason": "bank_statement_no_mirror"}
    target = (subfolder or resolve_case_mirror_subfolder(doc_type)).strip().lower()
    try:
        result = _mirror(case_id, filename, data, subfolder=target)
    except Exception as exc:  # noqa: BLE001
        logger.warning("yandex disk case mirror failed: %s", exc)
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
    if result.get("skipped"):
        return result
    if not result.get("ok"):
        logger.warning(
            "yandex disk case mirror not ok case_id=%s err=%s detail=%s",
            (case_id or "")[:36],
            result.get("error") or result.get("status_code"),
            (result.get("detail") or "")[:200],
        )
    elif result.get("ok"):
        maybe_export_case_chat_throttled(case_id)
    return result


def format_case_chat_markdown(
    case_id: str,
    messages: list[dict[str, Any]],
) -> str:
    """Markdown-экспорт ленты чата для Disk (канон сообщений — БД)."""
    from sfrfr.services.case_chat_context import author_label

    lines = [
        f"# Case chat {case_id}",
        "",
        "Source of truth: Supabase case_messages. This file is a best-effort mirror.",
        "",
    ]
    if not messages:
        lines.append("(empty)")
        return "\n".join(lines) + "\n"
    for row in messages:
        if not isinstance(row, dict):
            continue
        stamp = str(row.get("created_at") or "")[:19]
        label = author_label(str(row.get("author_kind") or ""))
        body = str(row.get("body") or "").strip()
        if not body:
            continue
        lines.append(f"## {stamp} · {label}")
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def export_case_chat_to_disk_safe(
    case_id: str,
    *,
    limit: int = 200,
) -> dict[str, Any]:
    """Снимок истории чата → disk:/SFRFR-cases/{case_id}/chat/history.md."""
    cid = (case_id or "").strip()
    if not cid:
        return {"ok": False, "error": "invalid_case_id"}
    messages: list[dict[str, Any]] = []
    try:
        from sfrfr.db.session import get_supabase_client

        cap = max(1, min(int(limit), 500))
        rows = (
            get_supabase_client()
            .table("case_messages")
            .select("id, author_kind, body, created_at")
            .eq("case_id", cid)
            .order("created_at", desc=True)
            .limit(cap)
            .execute()
            .data
            or []
        )
        messages = list(reversed([r for r in rows if isinstance(r, dict)]))
        content = format_case_chat_markdown(cid, messages).encode("utf-8")
        result = upload_case_chat_history(cid, content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("yandex disk chat export failed: %s", exc)
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
    if result.get("skipped"):
        return result
    if not result.get("ok"):
        logger.warning(
            "yandex disk chat export not ok case_id=%s err=%s",
            cid[:36],
            result.get("error") or result.get("status_code"),
        )
    else:
        result = {**result, "case_id": cid, "messages": len(messages)}
        _last_chat_export_at[cid.lower()] = time.monotonic()
    return result


def maybe_export_case_chat_throttled(case_id: str | None) -> dict[str, Any]:
    """Best-effort экспорт чата не чаще интервала на дело."""
    cid = (case_id or "").strip()
    if not cid:
        return {"ok": False, "skipped": True, "reason": "no_case_id"}
    key = cid.lower()
    now = time.monotonic()
    prev = _last_chat_export_at.get(key)
    if prev is not None and (now - prev) < _CHAT_EXPORT_MIN_INTERVAL_SEC:
        return {
            "ok": False,
            "skipped": True,
            "reason": "throttled",
            "retry_after_sec": int(_CHAT_EXPORT_MIN_INTERVAL_SEC - (now - prev)),
        }
    result = export_case_chat_to_disk_safe(cid)
    if result.get("ok"):
        _last_chat_export_at[key] = time.monotonic()
    return result
