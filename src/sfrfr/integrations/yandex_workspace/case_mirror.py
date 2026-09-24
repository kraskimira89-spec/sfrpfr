"""Best-effort зеркало документов дела на Яндекс.Диск (SFRFR-cases/{ФИО}/)."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sfrfr.integrations.yandex_workspace.disk import (
    CASES_FOLDER,
    delete_case_path,
    ensure_case_layout,
    list_case_dir,
    move_case_path,
    upload_case_chat_history,
)
from sfrfr.integrations.yandex_workspace.disk import (
    mirror_case_document as _mirror,
)
from sfrfr.services.document_ingest import SIGNED_DOC_TYPES
from sfrfr.utils.case_folder_name import format_case_disk_folder_name

logger = logging.getLogger(__name__)

_UUID_FOLDER_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_OUTGOING_DOC_TYPES = SIGNED_DOC_TYPES | {
    "application",
    "draft_application",
    "staff_application",
    "prepared_application",
}

_CHAT_EXPORT_MIN_INTERVAL_SEC = 900
_last_chat_export_at: dict[str, float] = {}


def resolve_case_mirror_subfolder(doc_type: str | None) -> str:
    """incoming = сканы клиента; outgoing = заявления / подписанные комплекты."""
    dtype = str(doc_type or "").strip().lower()
    if dtype in _OUTGOING_DOC_TYPES:
        return "outgoing"
    return "incoming"


def lookup_case_client_full_name(case_id: str) -> str | None:
    """ФИО клиента дела из БД (имя папки на Диске). Без телефона/СНИЛС."""
    cid = (case_id or "").strip()
    if not cid:
        return None
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("cases")
            .select("id, clients(full_name)")
            .eq("id", cid)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return None
        client = rows[0].get("clients") if isinstance(rows[0], dict) else None
        if isinstance(client, list):
            client = client[0] if client else None
        if not isinstance(client, dict):
            return None
        name = str(client.get("full_name") or "").strip()
        return name or None
    except Exception as exc:  # noqa: BLE001
        logger.info("case client full_name lookup skipped: %s", type(exc).__name__)
        return None


def _disk_folder_exists(folder: str) -> bool:
    result = list_case_dir(f"{CASES_FOLDER}/{folder}")
    return bool(result.get("ok"))


def sync_case_disk_folder_name_safe(
    case_id: str,
    *,
    full_name: str | None = None,
) -> dict[str, Any]:
    """Как только известно ФИО — папка на Диске = ФИО (не UUID).

    Best-effort: rename UUID→ФИО, либо создать layout, либо migrate дубля.
    """
    cid = (case_id or "").strip()
    if not cid or not _UUID_FOLDER_RE.match(cid):
        return {"ok": False, "skipped": True, "reason": "invalid_case_id"}
    cid = cid.lower()
    fio = full_name if full_name is not None else lookup_case_client_full_name(cid)
    folder = format_case_disk_folder_name(fio, case_id=cid)
    if not folder or _UUID_FOLDER_RE.match(folder) or folder.lower() == cid:
        return {
            "ok": False,
            "skipped": True,
            "reason": "no_fio",
            "case_id": cid,
        }
    try:
        uuid_exists = _disk_folder_exists(cid)
        fio_exists = _disk_folder_exists(folder)
        if uuid_exists and not fio_exists:
            moved = move_case_path(f"{CASES_FOLDER}/{cid}", f"{CASES_FOLDER}/{folder}")
            if moved.get("ok"):
                return {
                    "ok": True,
                    "action": "renamed",
                    "case_id": cid,
                    "folder_name": folder,
                }
            return {
                "ok": False,
                "action": "rename_failed",
                "case_id": cid,
                "folder_name": folder,
                "detail": moved.get("detail") or moved.get("error"),
            }
        if uuid_exists and fio_exists:
            from sfrfr.integrations.yandex_workspace.case_cleanup import (
                _content_names,
                read_case_tree,
            )

            missing = _content_names(read_case_tree(cid)) - _content_names(
                read_case_tree(folder)
            )
            if missing:
                return {
                    "ok": True,
                    "action": "keep_uuid",
                    "case_id": cid,
                    "folder_name": folder,
                    "missing_count": len(missing),
                }
            deleted = delete_case_path(f"{CASES_FOLDER}/{cid}")
            return {
                "ok": bool(deleted.get("ok")),
                "action": "deleted_duplicate" if deleted.get("ok") else "delete_failed",
                "case_id": cid,
                "folder_name": folder,
                "detail": deleted.get("detail") or deleted.get("error"),
            }
        if not fio_exists:
            layout = ensure_case_layout(cid, folder_name=folder)
            if layout.get("ok") or layout.get("skipped"):
                return {
                    "ok": True,
                    "action": "created",
                    "case_id": cid,
                    "folder_name": folder,
                }
            return {
                "ok": False,
                "action": "create_failed",
                "case_id": cid,
                "folder_name": folder,
                "detail": layout.get("error"),
            }
        return {
            "ok": True,
            "action": "already",
            "case_id": cid,
            "folder_name": folder,
        }
    except Exception as exc:  # noqa: BLE001
        logger.info("case disk folder sync skipped: %s", type(exc).__name__)
        return {
            "ok": False,
            "skipped": True,
            "reason": type(exc).__name__,
            "case_id": cid,
            "folder_name": folder,
        }


def sync_client_cases_disk_folders_safe(
    client_id: str,
    *,
    full_name: str | None = None,
) -> dict[str, Any]:
    """Переименовать папки всех дел клиента, когда ФИО стало известно."""
    cid = (client_id or "").strip()
    if not cid:
        return {"ok": False, "skipped": True, "reason": "no_client_id"}
    try:
        from sfrfr.db.session import get_supabase_client

        rows = (
            get_supabase_client()
            .table("cases")
            .select("id")
            .eq("client_id", cid)
            .limit(50)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("client cases for disk sync skipped: %s", type(exc).__name__)
        return {"ok": False, "skipped": True, "reason": type(exc).__name__}
    results = [
        sync_case_disk_folder_name_safe(str(row.get("id") or ""), full_name=full_name)
        for row in rows
        if isinstance(row, dict) and row.get("id")
    ]
    return {
        "ok": True,
        "client_id": cid,
        "count": len(results),
        "results": results,
    }


def _persist_original_local(case_id: str, filename: str, data: bytes) -> str | None:
    """Локальная копия оригинала байт-в-байт (имя можно нормализовать для FS)."""
    try:
        from sfrfr.storage.local import save_upload

        path = save_upload(case_id, filename, data)
        return str(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("local original save failed: %s", type(exc).__name__)
        return None


def mirror_case_document_safe(
    case_id: str,
    filename: str,
    data: bytes,
    *,
    doc_type: str | None = None,
    subfolder: str | None = None,
    full_name: str | None = None,
    persist_local: bool = True,
) -> dict[str, Any]:
    """Оригинал (те же байты) → local uploads + Яндекс.Диск в папке по ФИО."""
    dtype = str(doc_type or "").strip().lower()
    if dtype in {"bank_statement", "bank"}:
        return {"ok": False, "skipped": True, "reason": "bank_statement_no_mirror"}
    target = (subfolder or resolve_case_mirror_subfolder(doc_type)).strip().lower()
    local_path = (
        _persist_original_local(case_id, filename, data) if persist_local else None
    )
    fio = full_name if full_name is not None else lookup_case_client_full_name(case_id)
    folder_name = format_case_disk_folder_name(fio, case_id=case_id)
    if folder_name and not _UUID_FOLDER_RE.match(folder_name):
        sync_case_disk_folder_name_safe(case_id, full_name=fio)
    try:
        result = _mirror(
            case_id,
            filename,
            data,
            subfolder=target,
            folder_name=folder_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("yandex disk case mirror failed: %s", exc)
        return {
            "ok": False,
            "error": type(exc).__name__,
            "detail": str(exc)[:200],
            "local_path": local_path,
            "folder_name": folder_name,
        }
    if local_path:
        result = {**result, "local_path": local_path, "folder_name": folder_name}
    elif folder_name:
        result = {**result, "folder_name": folder_name}
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
        maybe_export_case_chat_throttled(case_id, folder_name=folder_name)
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
    folder_name: str | None = None,
) -> dict[str, Any]:
    """Снимок истории чата → disk:/SFRFR-cases/{ФИО}/chat/history.md."""
    cid = (case_id or "").strip()
    if not cid:
        return {"ok": False, "error": "invalid_case_id"}
    folder = folder_name or format_case_disk_folder_name(
        lookup_case_client_full_name(cid), case_id=cid
    )
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
        result = upload_case_chat_history(cid, content, folder_name=folder)
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
        result = {
            **result,
            "case_id": cid,
            "messages": len(messages),
            "folder_name": folder,
        }
        _last_chat_export_at[cid.lower()] = time.monotonic()
    return result


def maybe_export_case_chat_throttled(
    case_id: str | None,
    *,
    folder_name: str | None = None,
) -> dict[str, Any]:
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
    result = export_case_chat_to_disk_safe(cid, folder_name=folder_name)
    if result.get("ok"):
        _last_chat_export_at[key] = time.monotonic()
    return result
