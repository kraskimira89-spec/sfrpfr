"""Нормализация и проверка дублей исходящих staff/system сообщений."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

_WS_RE = re.compile(r"\s+")


def normalize_message_body(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip()).casefold()


def _parse_created(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        s = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def find_duplicate_staff_message(
    rows: list[dict[str, Any]],
    *,
    body: str,
    template_code: str | None = None,
    within_hours: float = 24.0,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Найти staff/system с тем же нормализованным телом (или template_code) за окно."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=within_hours)
    target = normalize_message_body(body)
    code = (template_code or "").strip()
    best: dict[str, Any] | None = None
    for row in rows:
        kind = str(row.get("author_kind") or "")
        if kind not in ("staff", "system"):
            continue
        created = _parse_created(row.get("created_at"))
        if created is None or created < cutoff:
            continue
        raw_body = str(row.get("body") or "")
        if code and f"[template:{code}]" in raw_body.casefold():
            best = row
            break
        if normalize_message_body(raw_body) == target:
            best = row
            break
    return best


def count_same_messages(
    rows: list[dict[str, Any]],
    *,
    body: str,
    template_code: str | None = None,
    within_hours: float = 48.0,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=within_hours)
    target = normalize_message_body(body)
    code = (template_code or "").strip()
    n = 0
    for row in rows:
        kind = str(row.get("author_kind") or "")
        if kind not in ("staff", "system"):
            continue
        created = _parse_created(row.get("created_at"))
        if created is None or created < cutoff:
            continue
        raw_body = str(row.get("body") or "")
        if code and f"[template:{code}]" in raw_body.casefold():
            n += 1
            continue
        if normalize_message_body(raw_body) == target:
            n += 1
    return n


def required_docs_missing(case: dict[str, Any]) -> list[str]:
    docs = case.get("documents") or []
    items = case.get("checklist_items") or []

    def has_doc(needles: list[str]) -> bool:
        for d in docs:
            blob = f"{d.get('doc_type') or ''} {d.get('storage_path') or ''}".lower()
            if any(n in blob for n in needles):
                return True
        return False

    def checklist_ok(pattern: re.Pattern[str]) -> bool:
        matched = [i for i in items if pattern.search(str(i.get("title") or ""))]
        if not matched:
            return False
        return all(i.get("status") == "done" for i in matched)

    missing: list[str] = []
    has_ils = has_doc(["ils", "илс", "сзи"]) or checklist_ok(re.compile(r"илс|выписк", re.I))
    has_labor = has_doc(["labor", "труд", "employment"]) or checklist_ok(
        re.compile(r"труд|стаж", re.I)
    )
    if not has_ils:
        missing.append("выписка ИЛС")
    if not has_labor:
        missing.append("трудовая / сведения о стаже")
    return missing


def has_service_consent(
    case: dict[str, Any],
    audit_rows: list[dict[str, Any]] | None = None,
) -> bool:
    if str(case.get("b2c_status") or "") != "lead":
        return True
    rows = audit_rows if audit_rows is not None else (case.get("audit") or [])
    return any(str(r.get("action") or "") == "service_consent_recorded" for r in rows)
