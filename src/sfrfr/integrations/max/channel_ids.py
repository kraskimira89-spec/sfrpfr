"""Обнаруженные chat_id каналов/групп MAX (локальный ops-store).

GET /chats с июня 2026 не поддерживается — ID собираем из webhook-событий
(bot_added, message_created в канале) и сохраняем для публикации.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path("var") / "max_channel_ids.json"


def store_path() -> Path:
    return _DEFAULT_PATH


def remember_chat_id(
    chat_id: int | str | None,
    *,
    source: str,
    title: str | None = None,
    update_type: str | None = None,
) -> dict[str, Any] | None:
    """Сохранить chat_id, если ещё не известен. Возвращает запись или None."""
    if chat_id is None or str(chat_id).strip() == "":
        return None
    cid = str(chat_id).strip()
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _load(path)
    chats_raw = data.setdefault("chats", {})
    if not isinstance(chats_raw, dict):
        chats_raw = {}
        data["chats"] = chats_raw
    items: dict[str, Any] = chats_raw
    now = datetime.now(UTC).isoformat()
    prev_raw = items.get(cid)
    prev: dict[str, Any] = prev_raw if isinstance(prev_raw, dict) else {}
    entry = {
        "chat_id": cid,
        "source": source,
        "update_type": update_type or prev.get("update_type"),
        "title": title or prev.get("title"),
        "first_seen_at": prev.get("first_seen_at") or now,
        "last_seen_at": now,
    }
    items[cid] = entry
    data["updated_at"] = now
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "max_channel_chat_id_seen chat_id=%s source=%s update_type=%s → set MAX_CHANNEL_CHAT_ID=%s",
        cid,
        source,
        update_type or "",
        cid,
    )
    return entry


def list_known() -> list[dict[str, Any]]:
    data = _load(store_path())
    chats = data.get("chats") or {}
    if not isinstance(chats, dict):
        return []
    rows = [v for v in chats.values() if isinstance(v, dict)]
    rows.sort(key=lambda r: str(r.get("last_seen_at") or ""), reverse=True)
    return rows


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"chats": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"chats": {}}
    return raw if isinstance(raw, dict) else {"chats": {}}
