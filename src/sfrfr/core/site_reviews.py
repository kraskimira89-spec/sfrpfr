"""Очередь цитат для главной: pending → published (без автопубликации в рейтинг)."""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STORE_LOCK = threading.Lock()
_DEFAULT_PATH = Path("var") / "site_reviews.json"

_PDN_HINT = re.compile(
    r"(?i)(\b\d{3}[- ]?\d{3}[- ]?\d{3}[ ]?\d{2}\b|"  # СНИЛС-подобное
    r"\bпаспорт\b|\bснилс\b|"
    r"\b\d{4,}\s*₽|\b\d{4,}\s*руб)",
)


def _store_path() -> Path:
    return _DEFAULT_PATH


def _empty() -> dict[str, Any]:
    return {"items": []}


def _load() -> dict[str, Any]:
    path = _store_path()
    if not path.is_file():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            return _empty()
        return data
    except Exception:  # noqa: BLE001
        return _empty()


def _save(data: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sanitize_text(text: str) -> str:
    cleaned = " ".join((text or "").split()).strip()
    return cleaned[:600]


def looks_unsafe(text: str) -> bool:
    if not text or len(text) < 15:
        return True
    if _PDN_HINT.search(text):
        return True
    banned = ("поставьте 5", "ставьте пять", "гарантируем перерасчёт", "повысили пенсию")
    lower = text.lower()
    return any(b in lower for b in banned)


def enqueue_quote(
    *,
    text: str,
    source: str = "anketa",
    consent: bool = False,
    publish_consent: bool = False,
) -> dict[str, Any] | None:
    """
    Положить цитату в очередь модерации.
    Без consent или при небезопасном тексте — None / queued=False.
    Без publish_consent — статус feedback (внутренняя ОС, не на витрину).
    """
    if not consent:
        return None
    body = _sanitize_text(text)
    if looks_unsafe(body):
        return {"ok": False, "queued": False, "reason": "unsafe_or_short"}

    status = "pending" if publish_consent else "feedback"
    item = {
        "id": str(uuid.uuid4()),
        "text": body,
        "source": (source or "anketa")[:32],
        "status": status,
        "publish_consent": bool(publish_consent),
        "created_at": datetime.now(UTC).isoformat(),
        "published_at": None,
    }
    with _STORE_LOCK:
        data = _load()
        data["items"].insert(0, item)
        # Не раздуваем файл
        data["items"] = data["items"][:500]
        _save(data)
    return {
        "ok": True,
        "queued": True,
        "id": item["id"],
        "status": status,
        "publish_consent": bool(publish_consent),
    }


def list_published(*, limit: int = 6) -> list[dict[str, Any]]:
    with _STORE_LOCK:
        items = _load().get("items") or []
    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("status") or "") != "published":
            continue
        out.append(
            {
                "id": str(raw.get("id") or ""),
                "text": str(raw.get("text") or ""),
                "source": str(raw.get("source") or ""),
                "published_at": raw.get("published_at"),
            }
        )
        if len(out) >= max(1, min(limit, 24)):
            break
    return out


def list_pending(*, limit: int = 50) -> list[dict[str, Any]]:
    with _STORE_LOCK:
        items = _load().get("items") or []
    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("status") or "") != "pending":
            continue
        out.append(dict(raw))
        if len(out) >= limit:
            break
    return out


def get_item(item_id: str) -> dict[str, Any] | None:
    """Найти отзыв по id (для модерации / уведомлений)."""
    needle = (item_id or "").strip()
    if not needle:
        return None
    with _STORE_LOCK:
        items = _load().get("items") or []
    for raw in items:
        if isinstance(raw, dict) and str(raw.get("id") or "") == needle:
            return dict(raw)
    return None


def set_status(item_id: str, status: str) -> dict[str, Any]:
    status = status.strip().lower()
    if status not in {"pending", "published", "rejected", "feedback"}:
        return {"ok": False, "error": "bad_status"}
    with _STORE_LOCK:
        data = _load()
        found = None
        for raw in data["items"]:
            if isinstance(raw, dict) and str(raw.get("id")) == item_id:
                raw["status"] = status
                raw["published_at"] = (
                    datetime.now(UTC).isoformat() if status == "published" else None
                )
                found = dict(raw)
                break
        if not found:
            return {"ok": False, "error": "not_found"}
        _save(data)
    return {"ok": True, "item": found}
