"""Очередь цитат для главной: pending → published (без автопубликации в рейтинг)."""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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

_MONTHS_RU_GENITIVE = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
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
    if _has_actionable_pdn(cleaned):
        return ""
    banned = ("поставьте 5", "ставьте пять", "гарантируем перерасчёт", "повысили пенсию")
    lower = cleaned.lower()
    if any(b in lower for b in banned):
        return ""
    return cleaned[:40]


def _format_review_date(item: dict[str, Any]) -> str:
    """Полная дата публикации для подписи: «28 августа 2026» (МСК)."""
    status = str(item.get("status") or "").strip().lower()
    raw_ts = item.get("published_at")
    if status != "published" and not raw_ts:
        raw_ts = item.get("created_at")
    if not isinstance(raw_ts, str) or not raw_ts.strip():
        return ""
    try:
        dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dt = dt.astimezone(ZoneInfo("Europe/Moscow"))
    except ValueError:
        return ""
    month = _MONTHS_RU_GENITIVE[dt.month] if 1 <= dt.month <= 12 else ""
    if not month:
        return ""
    return f"{dt.day} {month} {dt.year}"


def review_byline(item: dict[str, Any]) -> str:
    """Подпись под цитатой: имя / «имя, город» · дата (дата — автоматически при публикации)."""
    stored = str(item.get("display_byline") or "").strip()
    if stored:
        return stored
    label = _sanitize_author_label(str(item.get("author_label") or ""))
    if not label:
        return ""
    date = _format_review_date(item)
    if not date:
        return ""
    return f"{label} · {date}"


def author_label_from_client(full_name: str, city: str = "") -> str:
    """Подпись из профиля кабинета: «Имя О. Город» (без фамилии целиком)."""
    parts = " ".join((full_name or "").split()).split()
    if not parts:
        return ""
    if len(parts) >= 3:
        label = f"{parts[1]} {parts[2][0]}."
    elif len(parts) == 2:
        label = f"{parts[1]} {parts[0][0]}."
    else:
        label = parts[0]
    city = " ".join((city or "").split()).strip()
    if city:
        label = f"{label} {city}"
    return _sanitize_author_label(label[:40])


def _has_author_label(item: dict[str, Any]) -> bool:
    return bool(_sanitize_author_label(str(item.get("author_label") or "")))


def looks_unsafe(text: str) -> bool:
    return review_text_issue(text) is not None


def enqueue_quote(
    *,
    text: str,
    source: str = "anketa",
    consent: bool = False,
    publish_consent: bool = False,
    author_label: str = "",
    client_id: str = "",
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
    if publish_consent and not label:
        return {"ok": False, "queued": False, "reason": "author_label_required"}
    item = {
        "id": str(uuid.uuid4()),
        "text": body,
        "source": (source or "anketa")[:32],
        "status": status,
        "publish_consent": bool(publish_consent),
        "author_label": label or None,
        "client_id": (client_id or "").strip() or None,
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
        byline = review_byline(row)
        if not byline:
            continue
        out.append(
            {
                "id": str(raw.get("id") or ""),
                "text": str(raw.get("text") or ""),
                "source": str(raw.get("source") or ""),
                "author_label": str(raw.get("author_label") or "") or None,
                "byline": byline,
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


def set_author_label(item_id: str, author_label: str) -> dict[str, Any]:
    """Задать подпись перед публикацией (модерация / CLI)."""
    label = _sanitize_author_label(author_label)
    if not label:
        return {"ok": False, "error": "bad_label"}
    needle = (item_id or "").strip()
    if not needle:
        return {"ok": False, "error": "not_found"}
    with _STORE_LOCK:
        data = _load()
        found = None
        for raw in data["items"]:
            if isinstance(raw, dict) and str(raw.get("id") or "") == needle:
                raw["author_label"] = label
                row = dict(raw)
                if str(row.get("status") or "") == "published":
                    raw["display_byline"] = review_byline(row)
                found = dict(raw)
                break
        if not found:
            return {"ok": False, "error": "not_found"}
        _save(data)
    return {"ok": True, "item": found}


def set_status(item_id: str, status: str) -> dict[str, Any]:
    status = status.strip().lower()
    if status not in {"pending", "published", "rejected", "feedback"}:
        return {"ok": False, "error": "bad_status"}
    with _STORE_LOCK:
        data = _load()
        found = None
        for raw in data["items"]:
            if isinstance(raw, dict) and str(raw.get("id")) == item_id:
                if status == "published" and not _has_author_label(raw):
                    return {"ok": False, "error": "author_label_required"}
                raw["status"] = status
                raw["published_at"] = (
                    datetime.now(UTC).isoformat() if status == "published" else None
                )
                if status == "published":
                    raw["display_byline"] = review_byline(dict(raw))
                elif status != "published":
                    raw["display_byline"] = None
                found = dict(raw)
                break
        if not found:
            return {"ok": False, "error": "not_found"}
        _save(data)
    return {"ok": True, "item": found}
