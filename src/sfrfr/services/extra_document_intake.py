"""Дополнительные документы на любом этапе воронки.

Не сбрасывают оплату/согласования/этап 2. Привязка почты — только opaque-токен,
не ФИО/имя файла/адрес отправителя.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any  # noqa: TC003 — используется в публичных сигнатурах
from urllib.parse import quote

from sfrfr.core.config import get_settings

CATEGORIES: list[dict[str, str]] = [
    {"code": "children", "label": "Дети (свидетельство и др.)"},
    {"code": "stazh", "label": "Стаж / архивная справка"},
    {"code": "guardianship", "label": "Опекунство"},
    {"code": "contract", "label": "Договор"},
    {"code": "other", "label": "Другое"},
    {"code": "unknown", "label": "Не знаю — уточнит специалист"},
]

_CATEGORY_CODES = {c["code"] for c in CATEGORIES}

RECEIVED_CLIENT_MESSAGE = (
    "Документ получен и добавлен в дело. Специалист проверит его и сообщит, "
    "нужны ли уточнения. Повторно отправлять файл не нужно. "
    "Оплата и согласования не сбрасываются автоматически."
)

REJECTED_OR_FAILED_HINT = (
    "Файл не сохранён или не прошёл проверку. Исправьте проблему и загрузите снова. "
    "Пока специалист не проверил документ, он не считается принятым."
)

# Статусы доп. документа для сотрудника (не ingest_status хранилища).
REVIEW_STATUSES: frozenset[str] = frozenset(
    {"received", "checked", "needs_clarification"}
)
REVIEW_STATUS_LABELS_RU: dict[str, str] = {
    "received": "Получен",
    "checked": "Проверен",
    "needs_clarification": "Нужно уточнение",
}

_TOKEN_RE = re.compile(r"\[?\s*SFRFR-DOC\s+([A-Za-z0-9_-]{8,64})\s*\]?", re.I)
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def category_to_doc_type(category: str | None) -> str:
    code = (category or "unknown").strip().lower()
    if code not in _CATEGORY_CODES:
        code = "unknown"
    return f"extra_{code}"


def doc_type_is_extra(doc_type: str | None) -> bool:
    return str(doc_type or "").strip().lower().startswith("extra_")


def extra_upload_preserves_funnel(doc_type: str | None) -> bool:
    """True: не возвращать дело на этап «Документы», не трогать оплату/согласования."""
    return doc_type_is_extra(doc_type)


def should_reset_funnel_on_extra_upload(doc_type: str | None) -> bool:
    """Обратная к preserve (для тестов/читаемости)."""
    return not extra_upload_preserves_funnel(doc_type)


def staff_review_task_title(
    *,
    category: str | None = None,
    may_affect_analysis: bool = False,
) -> str:
    base = "Проверить новый документ"
    cat = (category or "").strip().lower()
    if cat and cat in _CATEGORY_CODES and cat != "unknown":
        label = next(c["label"] for c in CATEGORIES if c["code"] == cat)
        base = f"{base}: {label}"
    if may_affect_analysis:
        base = f"{base} (может затронуть разбор)"
    return base


def _token_secret(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    settings = get_settings()
    raw = (
        getattr(settings, "document_mail_bind_secret", None)
        or settings.yandex_oauth_access_token
        or "dev-only-document-mail-bind"
    )
    return str(raw).strip() or "dev-only-document-mail-bind"


def make_case_mail_token(case_id: str, *, secret: str | None = None) -> str:
    """Непрозрачный токен привязки письма к делу (не UUID дела)."""
    cid = (case_id or "").strip().lower()
    digest = hmac.new(
        _token_secret(secret).encode("utf-8"),
        cid.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    # короткий, без сырого UUID
    return digest[:20]


def verify_case_mail_token(case_id: str, token: str, *, secret: str | None = None) -> bool:
    expected = make_case_mail_token(case_id, secret=secret)
    return hmac.compare_digest(expected, (token or "").strip())


def extract_mail_token(subject: str | None) -> str | None:
    m = _TOKEN_RE.search(subject or "")
    return m.group(1) if m else None


def bind_case_from_mail_subject(
    subject: str | None,
    *,
    secret: str | None = None,
    known_case_ids: list[str],
    sender: str | None = None,  # намеренно не используем для привязки
) -> str | None:
    """Привязка только по opaque-токену. sender/ФИО игнорируются."""
    _ = sender  # запрещено использовать как единственный признак
    token = extract_mail_token(subject)
    if not token:
        return None
    for cid in known_case_ids:
        if verify_case_mail_token(str(cid), token, secret=secret):
            return str(cid)
    return None


def build_mail_compose(
    *,
    case_id: str,
    inbox: str,
    secret: str | None = None,
) -> dict[str, str]:
    token = make_case_mail_token(case_id, secret=secret)
    subject = f"Документы к делу [SFRFR-DOC {token}]"
    body = (
        "Здравствуйте!\n\n"
        "Прикрепите файлы ответом на это письмо. "
        "Не удаляйте код [SFRFR-DOC …] из темы — по нему письмо попадёт в ваше дело.\n\n"
        "Специалист проверит документы и напишет, если нужны уточнения.\n"
    )
    to = (inbox or "").strip()
    mailto = (
        f"mailto:{quote(to, safe='@.+_-')}?subject={quote(subject)}&body={quote(body)}"
    )
    return {
        "to": to,
        "subject": subject,
        "body": body,
        "mailto": mailto,
        "token_hint": "SFRFR-DOC (не сообщайте посторонним)",
    }


def notify_extra_document_received(
    *,
    repo: Any,
    case_id: str,
    document_id: str,
    doc_type: str | None,
    actor_id: str | None,
    may_affect_analysis: bool = False,
    upload_source: str | None = None,
) -> dict[str, Any]:
    """Задача сотруднику + audit. Не меняет pipeline/b2c/orders."""
    if not doc_type_is_extra(doc_type):
        return {"ok": False, "skipped": True, "reason": "not_extra"}
    cat = str(doc_type or "").removeprefix("extra_") or "unknown"
    title = staff_review_task_title(category=cat, may_affect_analysis=may_affect_analysis)
    note = f"document_id={document_id}; source=upload; category={cat}"
    try:
        ExtraDocumentReviewStore().mark_received(
            document_id,
            case_id=case_id,
            source=upload_source or "cabinet",
            may_affect_analysis=may_affect_analysis,
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        repo.upsert_checklist_item(
            case_id,
            title=title,
            item_type="extra_document_review",
            owner="expert",
            actor_id=actor_id,
            note=note,
            sort_order=5,
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        repo.audit(case_id, actor_id, f"extra_document_received:{document_id[:8]}")
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "client_message": RECEIVED_CLIENT_MESSAGE,
        "preserves_funnel": True,
        "task_title": title,
        "review_status": "received",
    }


def request_analysis_update_review(
    *,
    repo: Any,
    case_id: str,
    document_id: str,
    actor_id: str | None,
    note: str | None = None,
) -> dict[str, Any]:
    """Сотрудник подтвердил: нужно обновить разбор. Без сброса оплаты/согласований."""
    store = ExtraDocumentReviewStore()
    row = store.set_status(
        document_id,
        status="needs_clarification",
        actor_id=actor_id,
        analysis_update_needed=True,
        note=note,
    )
    title = "Доп. документ: обновить разбор (подтверждено сотрудником)"
    try:
        repo.upsert_checklist_item(
            case_id,
            title=title,
            item_type="extra_document_analysis_update",
            owner="expert",
            actor_id=actor_id,
            note=f"document_id={document_id}; {(note or '').strip()}"[:500],
            sort_order=4,
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        repo.audit(case_id, actor_id, f"extra_document_analysis_update:{document_id[:8]}")
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "review": row,
        "preserves_funnel": True,
        "task_title": title,
    }


def default_unbound_root() -> Path:
    root = Path(get_settings().storage_local_path).resolve()
    parent = root.parent if root.name.lower() in {"uploads", "local"} else root
    return parent / "mail_inbound_unbound"


def default_mail_processed_root() -> Path:
    root = Path(get_settings().storage_local_path).resolve()
    parent = root.parent if root.name.lower() in {"uploads", "local"} else root
    return parent / "mail_inbound_processed"


def default_extra_review_root() -> Path:
    root = Path(get_settings().storage_local_path).resolve()
    parent = root.parent if root.name.lower() in {"uploads", "local"} else root
    return parent / "extra_document_reviews"


class ExtraDocumentReviewStore:
    """Статусы Получен / Проверен / Нужно уточнение по document_id."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_extra_review_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._index = self.root / "index.json"

    def _load(self) -> dict[str, Any]:
        if not self._index.is_file():
            return {"by_document_id": {}}
        raw = json.loads(self._index.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"by_document_id": {}}
        by = raw.get("by_document_id")
        return {"by_document_id": dict(by) if isinstance(by, dict) else {}}

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self._index.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._index)

    def get(self, document_id: str) -> dict[str, Any] | None:
        did = (document_id or "").strip()
        if not did:
            return None
        row = self._load()["by_document_id"].get(did)
        return dict(row) if isinstance(row, dict) else None

    def mark_received(
        self,
        document_id: str,
        *,
        case_id: str,
        source: str = "cabinet",
        may_affect_analysis: bool = False,
    ) -> dict[str, Any]:
        did = (document_id or "").strip()
        if not did:
            raise ValueError("document_id_required")
        with _LOCK:
            data = self._load()
            prev = data["by_document_id"].get(did)
            row: dict[str, Any] = {
                "document_id": did,
                "case_id": case_id,
                "status": "received",
                "source": (source or "cabinet")[:40],
                "may_affect_analysis": bool(may_affect_analysis),
                "analysis_update_needed": False,
                "note": None,
                "updated_at": _now(),
                "created_at": (
                    str(prev.get("created_at"))
                    if isinstance(prev, dict) and prev.get("created_at")
                    else _now()
                ),
            }
            data["by_document_id"][did] = row
            self._save(data)
            return dict(row)

    def set_status(
        self,
        document_id: str,
        *,
        status: str,
        actor_id: str | None = None,
        analysis_update_needed: bool | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        did = (document_id or "").strip()
        st = (status or "").strip().lower()
        if st not in REVIEW_STATUSES:
            raise ValueError("invalid_status")
        if not did:
            raise ValueError("document_id_required")
        with _LOCK:
            data = self._load()
            prev = data["by_document_id"].get(did)
            base: dict[str, Any] = dict(prev) if isinstance(prev, dict) else {
                "document_id": did,
                "case_id": None,
                "created_at": _now(),
                "source": "staff",
            }
            base["status"] = st
            base["updated_at"] = _now()
            base["actor_id"] = actor_id
            if analysis_update_needed is not None:
                base["analysis_update_needed"] = bool(analysis_update_needed)
            if note is not None:
                base["note"] = (note or "")[:500] or None
            data["by_document_id"][did] = base
            self._save(data)
            return dict(base)

    def list_for_case(self, case_id: str) -> list[dict[str, Any]]:
        cid = (case_id or "").strip()
        rows = [
            dict(v)
            for v in self._load()["by_document_id"].values()
            if isinstance(v, dict) and str(v.get("case_id") or "") == cid
        ]
        rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
        return rows


class UnboundMailQueue:
    """Письма без однозначной привязки — не кладём в «похожее» дело."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_unbound_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._index = self.root / "index.json"

    def _load_index(self) -> dict[str, Any]:
        if not self._index.is_file():
            return {"by_message_id": {}, "items": []}
        raw = json.loads(self._index.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"by_message_id": {}, "items": []}
        return {
            "by_message_id": dict(raw.get("by_message_id") or {}),
            "items": list(raw.get("items") or []),
        }

    def _save_index(self, data: dict[str, Any]) -> None:
        tmp = self._index.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._index)

    @staticmethod
    def _norm_mid(message_id: str) -> str:
        return (message_id or "").strip().lower()

    def get_by_message_id(self, message_id: str) -> dict[str, Any] | None:
        data = self._load_index()
        mid = self._norm_mid(message_id)
        item_id = data["by_message_id"].get(mid)
        if not item_id:
            return None
        for it in data["items"]:
            if isinstance(it, dict) and it.get("id") == item_id:
                return dict(it)
        return None

    def _blob_dir(self, item_id: str) -> Path:
        d = self.root / "blobs" / item_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _safe_blob_name(self, index: int, filename: str) -> str:
        stem = Path(filename or "attachment.bin").name
        stem = re.sub(r"[^\w.\-а-яА-ЯёЁ]+", "_", stem, flags=re.UNICODE)[:80]
        return f"{index:02d}_{stem or 'attachment.bin'}"

    def save_attachment_blobs(
        self,
        item_id: str,
        attachments: list[tuple[str, bytes, str]],
    ) -> list[dict[str, Any]]:
        """Сохранить байты до привязки. Письмо не считается обработанным без этого."""
        meta: list[dict[str, Any]] = []
        for i, (name, data, ctype) in enumerate(attachments[:20]):
            if not data:
                continue
            fname = self._safe_blob_name(i, name)
            path = self._blob_dir(item_id) / fname
            path.write_bytes(data)
            meta.append(
                {
                    "filename": Path(name or fname).name[:180],
                    "stored_as": fname,
                    "content_type": (ctype or "application/octet-stream")[:120],
                    "size": len(data),
                }
            )
        return meta

    def load_attachment_blobs(
        self, item_id: str
    ) -> list[tuple[str, bytes, str]]:
        data = self._load_index()
        item: dict[str, Any] | None = None
        for it in data["items"]:
            if isinstance(it, dict) and str(it.get("id") or "") == item_id:
                item = it
                break
        if item is None:
            return []
        out: list[tuple[str, bytes, str]] = []
        blob_root = self.root / "blobs" / item_id
        for meta in list(item.get("blob_meta") or []):
            if not isinstance(meta, dict):
                continue
            stored = str(meta.get("stored_as") or "")
            path = blob_root / stored
            if not path.is_file():
                continue
            out.append(
                (
                    str(meta.get("filename") or stored),
                    path.read_bytes(),
                    str(meta.get("content_type") or "application/octet-stream"),
                )
            )
        return out

    def enqueue(
        self,
        *,
        message_id: str,
        subject: str,
        sender: str,
        attachment_names: list[str],
        attachments: list[tuple[str, bytes, str]] | None = None,
    ) -> dict[str, Any]:
        with _LOCK:
            existing = self.get_by_message_id(message_id)
            if existing:
                return {**existing, "deduped": True}
            item_id = str(uuid.uuid4())
            blob_meta: list[dict[str, Any]] = []
            if attachments:
                blob_meta = self.save_attachment_blobs(item_id, attachments)
            names = list(attachment_names or [])[:20]
            if not names and blob_meta:
                names = [str(m.get("filename") or "") for m in blob_meta]
            item = {
                "id": item_id,
                "status": "needs_binding",
                "message_id": message_id,
                "subject": (subject or "")[:300],
                "sender": (sender or "")[:200],
                "attachment_names": names,
                "blob_meta": blob_meta,
                "blobs_saved": len(blob_meta),
                "created_at": _now(),
            }
            data = self._load_index()
            data["items"].append(item)
            data["by_message_id"][self._norm_mid(message_id)] = item["id"]
            self._save_index(data)
            return dict(item)

    def list_pending(self, *, limit: int = 50) -> list[dict[str, Any]]:
        data = self._load_index()
        rows = [
            dict(it)
            for it in data["items"]
            if isinstance(it, dict) and it.get("status") == "needs_binding"
        ]
        rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return rows[:limit]

    def mark_bound(
        self,
        item_id: str,
        *,
        case_id: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        """Ручная привязка письма к делу сотрудником (без авто-угадывания)."""
        iid = (item_id or "").strip()
        cid = (case_id or "").strip()
        if not iid or not cid:
            raise ValueError("item_id_and_case_id_required")
        with _LOCK:
            data = self._load_index()
            found: dict[str, Any] | None = None
            for it in data["items"]:
                if isinstance(it, dict) and str(it.get("id") or "") == iid:
                    found = it
                    break
            if found is None:
                raise KeyError("unbound_item_not_found")
            if found.get("status") == "bound" and str(found.get("case_id") or "") == cid:
                return dict(found)
            found["status"] = "bound"
            found["case_id"] = cid
            found["bound_at"] = _now()
            found["bound_by"] = actor_id
            self._save_index(data)
            return dict(found)

    def clear_blobs(self, item_id: str) -> None:
        blob_root = self.root / "blobs" / (item_id or "").strip()
        if not blob_root.is_dir():
            return
        for path in blob_root.iterdir():
            try:
                path.unlink()
            except OSError:
                pass
        try:
            blob_root.rmdir()
        except OSError:
            pass


class MailInboundProcessedStore:
    """Идемпотентность IMAP: message_id обработан только после save/queue."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_mail_processed_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._index = self.root / "index.json"
        self._last_success = self.root / "last_success.json"

    def _load(self) -> dict[str, Any]:
        if not self._index.is_file():
            return {"by_message_id": {}}
        raw = json.loads(self._index.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"by_message_id": {}}
        by = raw.get("by_message_id")
        return {"by_message_id": dict(by) if isinstance(by, dict) else {}}

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self._index.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._index)

    @staticmethod
    def _norm(message_id: str) -> str:
        return (message_id or "").strip().lower()

    def is_processed(self, message_id: str) -> bool:
        mid = self._norm(message_id)
        if not mid:
            return False
        return mid in self._load()["by_message_id"]

    def mark_processed(
        self,
        message_id: str,
        *,
        status: str,
        detail: str | None = None,
    ) -> None:
        mid = self._norm(message_id)
        if not mid:
            return
        with _LOCK:
            data = self._load()
            data["by_message_id"][mid] = {
                "status": status,
                "at": _now(),
                "detail": (detail or "")[:200] or None,
            }
            # ограничение роста
            keys = list(data["by_message_id"].keys())
            if len(keys) > 5000:
                for old in keys[: len(keys) - 4000]:
                    data["by_message_id"].pop(old, None)
            self._save(data)

    def record_poll_success(self, *, processed: int, skipped: int) -> dict[str, Any]:
        row = {
            "ok": True,
            "at": _now(),
            "processed": processed,
            "skipped": skipped,
        }
        tmp = self._last_success.with_suffix(".tmp")
        tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self._last_success)
        return row

    def last_success(self) -> dict[str, Any] | None:
        if not self._last_success.is_file():
            return None
        raw = json.loads(self._last_success.read_text(encoding="utf-8"))
        return dict(raw) if isinstance(raw, dict) else None


def bind_unbound_mail_to_case(
    *,
    item_id: str,
    case_id: str,
    actor_id: str | None,
    store_document_fn: Any,
    repo: Any,
    queue: UnboundMailQueue | None = None,
) -> dict[str, Any]:
    """Ручная привязка: сохранить сохранённые вложения в дело как extra_*."""
    q = queue or UnboundMailQueue()
    row = q.mark_bound(item_id, case_id=case_id, actor_id=actor_id)
    blobs = q.load_attachment_blobs(item_id)
    saved: list[dict[str, Any]] = []
    for filename, data, content_type in blobs:
        try:
            doc = store_document_fn(
                case_id=case_id,
                filename=filename,
                data=data,
                content_type=content_type or "application/octet-stream",
                doc_type=category_to_doc_type("unknown"),
                uploaded_by=actor_id,
                upload_source="email",
            )
        except Exception as exc:  # noqa: BLE001
            saved.append({"filename": filename, "ok": False, "error": type(exc).__name__})
            continue
        doc_id = str((doc or {}).get("id") or "")
        if doc_id:
            notify_extra_document_received(
                repo=repo,
                case_id=case_id,
                document_id=doc_id,
                doc_type=category_to_doc_type("unknown"),
                actor_id=actor_id,
                may_affect_analysis=True,
                upload_source="email",
            )
        saved.append({"filename": filename, "ok": True, "document_id": doc_id})
    if blobs and all(s.get("ok") for s in saved):
        q.clear_blobs(item_id)
    try:
        repo.upsert_checklist_item(
            case_id,
            title="Почта: вложения привязаны вручную",
            item_type="extra_document_mail_bind",
            owner="expert",
            actor_id=actor_id,
            note=f"unbound_id={item_id}; files={len(saved)}"[:500],
            sort_order=5,
        )
        repo.audit(case_id, actor_id, f"mail_inbound_bound:{item_id[:8]}")
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "item": row,
        "saved": saved,
        "preserves_funnel": True,
        "honest": True,
        "detail": (
            f"Письмо привязано к делу; сохранено вложений: "
            f"{sum(1 for s in saved if s.get('ok'))}/{len(saved) or 0}."
        ),
    }
