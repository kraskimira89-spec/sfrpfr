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

_PDN_SNILS = re.compile(r"\b\d{3}[- ]?\d{3}[- ]?\d{3}[ ]?\d{2}\b")
_PDN_MONEY = re.compile(r"(?i)\b\d{4,}\s*(?:₽|руб\.?)")
_PDN_WORD = re.compile(r"(?i)\b(снилс|snils|паспорт|passport)\b")
_NEGATION = re.compile(r"(?i)(не\s|без\s|не\s+указы|не\s+пиш)")

_HINT_EXAMPLES = (
    "стало понятнее, какие документы собрать",
    "понравилось, что объяснили порядок действий",
)

_MONTHS_RU = (
    "",
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
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


def _is_hint_boilerplate(text: str) -> bool:
    """Текст подсказки с /otzyvy/, который люди копируют вместо своего отзыва."""
    lower = text.lower()
    hits = sum(1 for marker in _HINT_EXAMPLES if marker in lower)
    if hits >= 2:
        return True
    return hits >= 1 and "не пишите" in lower


def _has_actionable_pdn(text: str) -> bool:
    if _PDN_SNILS.search(text):
        return True
    if _PDN_MONEY.search(text):
        return True
    lower = text.lower()
    for match in _PDN_WORD.finditer(text):
        start = match.start()
        prefix = lower[max(0, start - 48) : start]
        if _NEGATION.search(prefix):
            continue
        return True
    return False


def review_text_issue(text: str) -> str | None:
    """
    Причина отклонения текста отзыва или None, если текст принимаем.
    Коды: too_short, hint_text, pdn_in_text, banned_phrase.
    """
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned or len(cleaned) < 15:
        return "too_short"
    if _is_hint_boilerplate(cleaned):
        return "hint_text"
    if _has_actionable_pdn(cleaned):
        return "pdn_in_text"
    banned = ("поставьте 5", "ставьте пять", "гарантируем перерасчёт", "повысили пенсию")
    lower = cleaned.lower()
    if any(b in lower for b in banned):
        return "banned_phrase"
    return None


def _sanitize_author_label(label: str) -> str:
    cleaned = " ".join((label or "").split()).strip()
    if not cleaned:
        return ""
    if len(cleaned) < 2:
        return ""
    if review_text_issue(cleaned) or _has_actionable_pdn(cleaned):
        return ""
    return cleaned[:40]


def review_byline(item: dict[str, Any]) -> str:
    """Подпись под цитатой на сайте: имя автора или нейтральный fallback."""
    label = _sanitize_author_label(str(item.get("author_label") or ""))
    if label:
        return label
    raw_ts = item.get("published_at") or item.get("created_at")
    if isinstance(raw_ts, str) and raw_ts.strip():
        try:
            dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            month = _MONTHS_RU[dt.month] if 1 <= dt.month <= 12 else ""
            if month:
                return f"Клиент · {month} {dt.year}"
        except ValueError:
            pass
    return "Клиент сервиса"


def looks_unsafe(text: str) -> bool:
    return review_text_issue(text) is not None


def enqueue_quote(
    *,
    text: str,
    source: str = "anketa",
    consent: bool = False,
    publish_consent: bool = False,
    author_label: str = "",
) -> dict[str, Any] | None:
    """
    Положить цитату в очередь модерации.
    Без consent или при небезопасном тексте — None / queued=False.
    Без publish_consent — статус feedback (внутренняя ОС, не на витрину).
    """
    if not consent:
        return None
    body = _sanitize_text(text)
    issue = review_text_issue(body)
    if issue:
        return {"ok": False, "queued": False, "reason": issue}

    status = "pending" if publish_consent else "feedback"
    label = _sanitize_author_label(author_label) if publish_consent else ""
    item = {
        "id": str(uuid.uuid4()),
        "text": body,
        "source": (source or "anketa")[:32],
        "status": status,
        "publish_consent": bool(publish_consent),
        "author_label": label or None,
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
        row = dict(raw)
        out.append(
            {
                "id": str(raw.get("id") or ""),
                "text": str(raw.get("text") or ""),
                "source": str(raw.get("source") or ""),
                "author_label": str(raw.get("author_label") or "") or None,
                "byline": review_byline(row),
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
