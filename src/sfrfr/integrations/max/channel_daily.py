"""Ежедневная очередь постов клиентского канала MAX (полуавто → ops DM)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUEUE_PATH = Path("scripts/assets/max-channel/daily-queue.json")
STARTER_PATH = Path("scripts/assets/max-channel/starter-posts.json")
STATE_PATH = Path("storage/max_channel_daily_state.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_queue(path: Path = QUEUE_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("daily-queue.json: ожидается объект")
    queue = data.get("queue")
    if not isinstance(queue, list) or not queue:
        raise ValueError("daily-queue.json: пустой queue")
    ids = [str(x).strip() for x in queue if str(x).strip()]
    if not ids:
        raise ValueError("daily-queue.json: нет id")
    return {**data, "queue": ids}


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {"sent_ids": [], "last_id": "", "last_at": "", "updated_at": ""}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"sent_ids": [], "last_id": "", "last_at": "", "updated_at": ""}
    sent = data.get("sent_ids") or []
    if not isinstance(sent, list):
        sent = []
    return {
        "sent_ids": [str(x) for x in sent if str(x).strip()],
        "last_id": str(data.get("last_id") or ""),
        "last_at": str(data.get("last_at") or ""),
        "updated_at": str(data.get("updated_at") or ""),
    }


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sent_ids": list(state.get("sent_ids") or []),
        "last_id": str(state.get("last_id") or ""),
        "last_at": str(state.get("last_at") or ""),
        "updated_at": _utc_now(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_post_id(queue: list[str], sent_ids: list[str]) -> str | None:
    sent = set(sent_ids)
    for post_id in queue:
        if post_id not in sent:
            return post_id
    return None


def load_post_by_id(post_id: str, path: Path = STARTER_PATH) -> dict[str, Any]:
    posts = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(posts, list):
        raise ValueError("starter-posts.json: ожидается массив")
    for item in posts:
        if isinstance(item, dict) and str(item.get("id") or "") == post_id:
            return item
    raise LookupError(f"пост id={post_id} не найден в {path}")


def mark_sent(post_id: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    current = dict(state or load_state())
    sent = list(current.get("sent_ids") or [])
    if post_id not in sent:
        sent.append(post_id)
    current["sent_ids"] = sent
    current["last_id"] = post_id
    current["last_at"] = _utc_now()
    save_state(current)
    return current


def peek_daily() -> dict[str, Any]:
    cfg = load_queue()
    state = load_state()
    nxt = next_post_id(list(cfg["queue"]), list(state.get("sent_ids") or []))
    return {
        "mode": cfg.get("mode") or "ops_review",
        "next_id": nxt,
        "queue": cfg["queue"],
        "sent_ids": state.get("sent_ids") or [],
        "last_id": state.get("last_id") or "",
        "done": nxt is None,
    }
