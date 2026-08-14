"""Черновики постов клиентского канала MAX — премодерация в канале команды."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sfrfr.core.config import get_settings

DraftStatus = Literal["pending", "published", "cancelled"]

# payload callback ≤ ~100 символов: id короткий
_PAYLOAD_PREFIX = "chdraft"


@dataclass
class ChannelDraft:
    id: str
    text: str
    cta_label: str = ""
    cta_kind: str = ""  # chat | url | ""
    cta_url: str = ""
    pin: bool = False
    source_id: str = ""  # id из starter-posts.json
    status: DraftStatus = "pending"
    created_at: str = ""
    updated_at: str = ""
    published_url: str = ""
    published_mid: str = ""
    waiting_edit_user_ids: list[str] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()


def default_drafts_path() -> Path:
    root = Path(get_settings().storage_local_path).resolve().parent
    return root / "max_channel_drafts.json"


class ChannelDraftStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_drafts_path()
        self._lock = threading.RLock()
        self._rows: dict[str, ChannelDraft] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._rows = {}
            return
        raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        rows = raw.get("rows") or {}
        known = {f.name for f in fields(ChannelDraft)}
        loaded: dict[str, ChannelDraft] = {}
        for key, data in rows.items():
            if not isinstance(data, dict):
                continue
            filtered = {k: v for k, v in data.items() if k in known}
            try:
                loaded[str(key)] = ChannelDraft(**filtered)
            except TypeError:
                continue
        self._rows = loaded

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"rows": {k: asdict(v) for k, v in self._rows.items()}}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def create(
        self,
        *,
        text: str,
        cta_label: str = "",
        cta_kind: str = "",
        cta_url: str = "",
        pin: bool = False,
        source_id: str = "",
        draft_id: str | None = None,
    ) -> ChannelDraft:
        body = (text or "").strip()
        if not body:
            raise ValueError("empty draft text")
        with self._lock:
            now = datetime.now(UTC).isoformat()
            did = (draft_id or "").strip() or uuid.uuid4().hex[:10]
            draft = ChannelDraft(
                id=did,
                text=body,
                cta_label=(cta_label or "").strip(),
                cta_kind=(cta_kind or "").strip(),
                cta_url=(cta_url or "").strip(),
                pin=bool(pin),
                source_id=(source_id or "").strip(),
                status="pending",
                created_at=now,
                updated_at=now,
            )
            self._rows[did] = draft
            self._save()
            return draft

    def get(self, draft_id: str) -> ChannelDraft | None:
        with self._lock:
            return self._rows.get((draft_id or "").strip())

    def update_text(self, draft_id: str, text: str) -> ChannelDraft | None:
        body = (text or "").strip()
        if not body:
            return None
        with self._lock:
            draft = self._rows.get((draft_id or "").strip())
            if not draft:
                return None
            draft.text = body
            draft.status = "pending"
            draft.waiting_edit_user_ids = []
            draft.touch()
            self._save()
            return draft

    def mark_waiting_edit(self, draft_id: str, user_id: str) -> ChannelDraft | None:
        uid = (user_id or "").strip()
        with self._lock:
            draft = self._rows.get((draft_id or "").strip())
            if not draft or not uid:
                return None
            if uid not in draft.waiting_edit_user_ids:
                draft.waiting_edit_user_ids.append(uid)
            draft.touch()
            self._save()
            return draft

    def clear_waiting_edit(self, draft_id: str, user_id: str | None = None) -> None:
        with self._lock:
            draft = self._rows.get((draft_id or "").strip())
            if not draft:
                return
            if user_id:
                draft.waiting_edit_user_ids = [
                    u for u in draft.waiting_edit_user_ids if u != user_id
                ]
            else:
                draft.waiting_edit_user_ids = []
            draft.touch()
            self._save()

    def find_waiting_for_user(self, user_id: str) -> ChannelDraft | None:
        uid = (user_id or "").strip()
        if not uid:
            return None
        with self._lock:
            pending = [
                d
                for d in self._rows.values()
                if d.status == "pending" and uid in d.waiting_edit_user_ids
            ]
            if not pending:
                return None
            pending.sort(key=lambda d: d.updated_at or d.created_at, reverse=True)
            return pending[0]

    def mark_published(
        self,
        draft_id: str,
        *,
        url: str = "",
        mid: str = "",
    ) -> ChannelDraft | None:
        with self._lock:
            draft = self._rows.get((draft_id or "").strip())
            if not draft:
                return None
            draft.status = "published"
            draft.published_url = (url or "").strip()
            draft.published_mid = (mid or "").strip()
            draft.waiting_edit_user_ids = []
            draft.touch()
            self._save()
            return draft


_store: ChannelDraftStore | None = None
_store_lock = threading.Lock()


def get_draft_store(path: Path | None = None) -> ChannelDraftStore:
    global _store
    with _store_lock:
        if path is not None:
            _store = ChannelDraftStore(path)
            return _store
        if _store is None:
            _store = ChannelDraftStore()
        return _store


def reset_draft_store(path: Path | None = None) -> ChannelDraftStore:
    global _store
    with _store_lock:
        _store = ChannelDraftStore(path or default_drafts_path())
        return _store


def publish_payload(draft_id: str) -> str:
    return f"{_PAYLOAD_PREFIX}:pub:{draft_id}"


def edit_payload(draft_id: str) -> str:
    """Callback: специалист пришлёт правку следующим сообщением в ops-бот."""
    return f"{_PAYLOAD_PREFIX}:edit:{draft_id}"


def parse_draft_callback(payload: str) -> tuple[str, str] | None:
    """Вернуть (action, draft_id) или None. action: pub | edit."""
    raw = (payload or "").strip()
    parts = raw.split(":")
    if len(parts) != 3 or parts[0] != _PAYLOAD_PREFIX:
        return None
    action, draft_id = parts[1], parts[2]
    if action not in {"pub", "edit"} or not draft_id:
        return None
    return action, draft_id


def review_keyboard(draft: ChannelDraft) -> list[dict[str, Any]]:
    """Кнопки: Опубликовать | Скопировать текст | Прислать правку."""
    text_for_clip = draft.text
    if len(text_for_clip.encode("utf-8")) > 4000:
        text_for_clip = text_for_clip[:3500] + "\n…"
    rows: list[list[dict[str, Any]]] = [
        [
            {
                "type": "callback",
                "text": "Опубликовать",
                "payload": publish_payload(draft.id),
                "intent": "positive",
            }
        ],
        [
            {
                "type": "clipboard",
                "text": "Скопировать текст",
                "payload": text_for_clip,
            }
        ],
        [
            {
                "type": "callback",
                "text": "Прислать правку",
                "payload": edit_payload(draft.id),
            }
        ],
    ]
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


def format_review_message(draft: ChannelDraft) -> str:
    lines = [
        "Черновик поста в клиентский канал",
        f"id: `{draft.id}`"
        + (f" (источник: {draft.source_id})" if draft.source_id else ""),
        "",
        "—" * 12,
        draft.text,
        "—" * 12,
        "",
    ]
    if draft.cta_label:
        target = draft.cta_url if draft.cta_kind == "url" else "личный чат MAX"
        lines.append(f"Кнопка у клиентов: «{draft.cta_label}» -> {target}")
        lines.append("")
    lines.extend(
        [
            "«Опубликовать» — сразу в канал клиентов.",
            "«Скопировать текст» -> поправьте -> вставьте сюда в этот чат "
            "(или нажмите «Прислать правку» и пришлите текст).",
            "Ответ с кнопкой «Опубликовать» придёт сюда же, в ops-бот — не в канал команды.",
        ]
    )
    return "\n".join(lines)


def looks_like_channel_post(text: str) -> bool:
    """Эвристика: длинный/многострочный текст в личке ops — это черновик поста."""
    body = (text or "").strip()
    if not body or body.startswith("/"):
        return False
    if len(body) >= 120:
        return True
    return len(body) >= 60 and ("\n" in body)


def client_cta_attachments(draft: ChannelDraft) -> list[dict[str, Any]] | None:
    from sfrfr.integrations.max.client import inline_link_keyboard

    settings = get_settings()
    label = draft.cta_label
    if not label:
        return None
    if draft.cta_kind == "chat":
        chat_url = (settings.max_chat_url or "").strip()
        if chat_url:
            return inline_link_keyboard(label, chat_url)
    if draft.cta_kind == "url" and draft.cta_url:
        return inline_link_keyboard(label, draft.cta_url)
    return None
