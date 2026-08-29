"""Лента переписки MAX ↔ дело: буфер до создания case + запись в case_messages."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sfrfr.core.config import get_settings
from sfrfr.integrations.max.intake import (
    BACK_LABEL,
    CALL_OPERATOR_LABEL,
    DOCS_ARTICLE_LABEL,
    DOCS_BASE_LABEL,
    DOCS_GOS_LABEL,
    DOCS_INFO_LABEL,
    DOCS_MISSING_LABEL,
    DOCS_SPECIAL_LABEL,
    DOCS_STAZH_LABEL,
    EMP_CONTINUE_LABEL,
    ILS_GOT_LABEL,
    ILS_MFC_LABEL,
    OPEN_CABINET_LABEL,
    OPEN_GOSUSLUGI_LABEL,
    RESTART_LABEL,
)

logger = logging.getLogger(__name__)

_MAX_PENDING_PER_USER = 250
_lock = threading.RLock()
_pending: dict[str, list[dict[str, str]]] = {}
_loaded = False

# Подписи кнопок сценария (payload → текст, как в MAX).
CALLBACK_LABELS: dict[str, str] = {
    "intake:whom:self": "За себя",
    "intake:whom:relative": "Помогаю близкому",
    "intake:operator": CALL_OPERATOR_LABEL,
    "intake:goal:operator": CALL_OPERATOR_LABEL,
    "intake:pension:before": "До пенсии",
    "intake:pension:assigned": "Пенсия назначена",
    "intake:problem:ils_stazh": "ИЛС и стаж",
    "intake:problem:north": "Северный или льготный",
    "intake:problem:documents": "Документы",
    "intake:problem:sfr_refusal": "Отказ СФР",
    "intake:ils:yes": "Есть выписка ИЛС",
    "intake:ils:need": "Нужно получить",
    "intake:ils:no": "Нет",
    "intake:ils:unknown": "Не знаю, как получить",
    "intake:ils_guide:done": ILS_GOT_LABEL,
    "intake:ils_guide:mfc": ILS_MFC_LABEL,
    "intake:emp:yes": "Да",
    "intake:emp:partial": "Часть документов",
    "intake:emp:no": "Нет",
    "intake:emp_guide:done": EMP_CONTINUE_LABEL,
    "intake:device:max": "С телефона",
    "intake:device:web": "С компьютера",
    "intake:device:help": "Нужна помощь",
    "intake:docs_info": DOCS_INFO_LABEL,
    "intake:docs:base": DOCS_BASE_LABEL,
    "intake:docs:stazh": DOCS_STAZH_LABEL,
    "intake:docs:special": DOCS_SPECIAL_LABEL,
    "intake:docs:gosuslugi": DOCS_GOS_LABEL,
    "intake:docs:missing": DOCS_MISSING_LABEL,
    "intake:docs:ils_howto": "Как получить ИЛС",
    "intake:restart": RESTART_LABEL,
    "intake:back": BACK_LABEL,
}


def _pending_path() -> Path:
    root = Path(get_settings().storage_local_path).resolve().parent
    return root / "max_chat_pending.json"


def _load_pending() -> None:
    global _loaded, _pending
    with _lock:
        if _loaded:
            return
        _loaded = True
        path = _pending_path()
        if not path.exists():
            _pending = {}
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8") or "{}")
            rows = raw.get("rows") or {}
            out: dict[str, list[dict[str, str]]] = {}
            for mid, items in rows.items():
                if not isinstance(items, list):
                    continue
                cleaned: list[dict[str, str]] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    body = str(item.get("body") or "").strip()
                    kind = str(item.get("author_kind") or "client").strip()
                    if not body:
                        continue
                    cleaned.append(
                        {
                            "author_kind": kind,
                            "body": body[:4000],
                            "created_at": str(
                                item.get("created_at") or datetime.now(UTC).isoformat()
                            ),
                        }
                    )
                if cleaned:
                    out[str(mid)] = cleaned[-_MAX_PENDING_PER_USER:]
            _pending = out
        except Exception as exc:  # noqa: BLE001
            logger.warning("max_chat_pending load failed: %s", exc)
            _pending = {}


def _save_pending() -> None:
    path = _pending_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"rows": _pending}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("max_chat_pending save failed: %s", exc)


def label_for_callback(payload: str) -> str:
    """Человекочитаемая подпись нажатой кнопки."""
    raw = (payload or "").strip()
    if not raw:
        return "кнопка"
    if raw in CALLBACK_LABELS:
        return CALLBACK_LABELS[raw]
    if raw.startswith("llmsoft:"):
        parts = raw.split(":", 2)
        soft = parts[2].strip() if len(parts) > 2 else ""
        return soft or "вариант ответа"
    if raw.startswith("svy:"):
        return "опрос понятности"
    if raw.startswith("review:"):
        return f"отзыв ({raw.split(':', 1)[-1]})"
    return raw


def format_button_press(payload: str) -> str:
    return f"Нажал кнопку: {label_for_callback(payload)}"


def keyboard_button_labels(attachments: list[dict[str, Any]] | None) -> list[str]:
    labels: list[str] = []
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        payload = att.get("payload") if isinstance(att.get("payload"), dict) else att
        rows = payload.get("buttons") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list):
                continue
            for btn in row:
                if not isinstance(btn, dict):
                    continue
                text = str(btn.get("text") or "").strip()
                if text:
                    labels.append(text)
                elif btn.get("type") == "link" and btn.get("url"):
                    labels.append(str(btn.get("text") or OPEN_GOSUSLUGI_LABEL))
    # link-кнопки кабинета тоже полезны в ленте
    extra = []
    for label in labels:
        if label in {OPEN_CABINET_LABEL, DOCS_ARTICLE_LABEL}:
            extra.append(label)
    return [x for x in labels if x]


def format_document_event(*, filename: str, doc_type: str | None = None) -> str:
    name = (filename or "файл").strip() or "файл"
    suffix = f" · {doc_type}" if (doc_type or "").strip() else ""
    return f"[Документ] {name}{suffix}"


def _insert_case_message(
    *,
    case_id: str,
    author_kind: str,
    body: str,
    created_at: str | None = None,
) -> None:
    from sfrfr.db.session import get_supabase_client

    row: dict[str, Any] = {
        "case_id": case_id,
        "author_kind": author_kind,
        "author_user_id": None,
        "body": body[:4000],
    }
    if created_at:
        row["created_at"] = created_at
    get_supabase_client().table("case_messages").insert(row).execute()


def _buffer(*, max_user_id: str, author_kind: str, body: str) -> None:
    _load_pending()
    mid = str(max_user_id).strip()
    if not mid or not body.strip():
        return
    with _lock:
        bucket = _pending.setdefault(mid, [])
        bucket.append(
            {
                "author_kind": author_kind,
                "body": body.strip()[:4000],
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        _pending[mid] = bucket[-_MAX_PENDING_PER_USER:]
        _save_pending()


def append_case_chat_message(
    *,
    case_id: str | None,
    max_user_id: str | None = None,
    author_kind: str,
    body: str,
) -> None:
    """Записать в case_messages или в буфер до появления дела.

    Важно: при ошибке insert (в т.ч. FK — «дела нет в БД») не терять текст —
    складываем в буфер по max_user_id, иначе клиент видит ответ бота в MAX,
    а в кабинете сотрудника реплики нет.
    """
    cid = (case_id or "").strip()
    text = (body or "").strip()
    mid = (max_user_id or "").strip()
    if not text:
        return
    if cid and len(cid) >= 32:
        try:
            _insert_case_message(case_id=cid, author_kind=author_kind, body=text)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "case_message append failed case=%s: %s; fallback_buffer=%s",
                cid[:8],
                exc,
                bool(mid),
            )
            if mid:
                _buffer(max_user_id=mid, author_kind=author_kind, body=text)
            return
    if mid:
        _buffer(max_user_id=mid, author_kind=author_kind, body=text)


def append_bot_case_message(
    *,
    case_id: str | None,
    max_user_id: str | None = None,
    text: str,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    body = (text or "").strip()
    if not body:
        return
    labels = keyboard_button_labels(attachments)
    if labels:
        body = f"{body}\n\n[Кнопки бота: {' · '.join(labels)}]"
    append_case_chat_message(
        case_id=case_id,
        max_user_id=max_user_id,
        author_kind="system",
        body=body,
    )


def append_client_case_message(
    *,
    case_id: str | None,
    max_user_id: str | None = None,
    text: str,
) -> None:
    append_case_chat_message(
        case_id=case_id,
        max_user_id=max_user_id,
        author_kind="client",
        body=text,
    )


def flush_pending_case_chat(*, max_user_id: str | None, case_id: str | None) -> int:
    """Слить буфер переписки в дело после создания case_id."""
    mid = (max_user_id or "").strip()
    cid = (case_id or "").strip()
    if not mid or not cid or len(cid) < 32:
        return 0
    _load_pending()
    with _lock:
        items = list(_pending.pop(mid, []) or [])
        _save_pending()
    if not items:
        return 0
    written = 0
    leftover: list[dict[str, str]] = []
    for item in items:
        try:
            _insert_case_message(
                case_id=cid,
                author_kind=str(item.get("author_kind") or "client"),
                body=str(item.get("body") or ""),
                created_at=str(item.get("created_at") or "") or None,
            )
            written += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("flush case_message failed case=%s: %s", cid[:8], exc)
            leftover.append(item)
    if leftover:
        with _lock:
            bucket = _pending.setdefault(mid, [])
            # Не дублировать уже записанное — вернуть только неудавшиеся.
            _pending[mid] = (leftover + bucket)[-_MAX_PENDING_PER_USER:]
            _save_pending()
    return written


def reset_pending_for_tests() -> None:
    """Только для unit-тестов."""
    global _pending, _loaded
    with _lock:
        _pending = {}
        _loaded = True
        path = _pending_path()
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
