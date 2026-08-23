"""Яндекс Трекер: клиент API для внутренних задач качества (очередь STAZH)."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

import httpx

from sfrfr.core.config import get_settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.tracker.yandex.net/v3"

ISSUE_TYPES = (
    "bug",
    "sla_incident",
    "channel_conflict",
    "process_improvement",
    "development",
    "content",
    "security_privacy",
    "analytics_hypothesis",
    "partner_request",
)

ISSUE_TYPE_LABELS_RU: dict[str, str] = {
    "bug": "Ошибка",
    "sla_incident": "Инцидент SLA",
    "channel_conflict": "Конфликт каналов",
    "process_improvement": "Улучшение процесса",
    "development": "Разработка",
    "content": "Контент",
    "security_privacy": "Безопасность / ПДн",
    "analytics_hypothesis": "Аналитическая гипотеза",
    "partner_request": "Партнёрский запрос",
}

DIRECTIONS = ("ops", "product", "dev", "content", "security", "partners")
SOURCES = ("cabinet", "max", "web", "amocrm", "staff", "analytics", "partner")
CHANNELS = ("max", "web", "phone", "email", "unknown")
AGE_BUCKETS = ("30m", "1d", "3d", "7d_plus")
REPEATABILITY = ("once", "recurring", "systemic")
PRIORITIES = ("critical", "high", "normal", "low")

PRIORITY_TO_TRACKER = {
    "critical": "critical",
    "high": "critical",
    "normal": "normal",
    "low": "minor",
}

# Паттерны запрещённого в тексте (санитар)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
_SNILS_RE = re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b")
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)
_CABINET_URL_RE = re.compile(
    r"https?://(?:cabinet|admin)\.proverkastaza\.ru[^\s]*",
    re.I,
)
_STORAGE_URL_RE = re.compile(r"https?://[^\s]*(storage|supabase|document)[^\s]*", re.I)


def case_ref_for(case_id: str, *, secret: str | None = None) -> str:
    """Псевдоним дела: sha256(case_id + salt)[:12]."""
    settings = get_settings()
    if secret is not None:
        salt = secret.strip()
    else:
        salt = (settings.tracker_case_ref_secret or settings.app_secret_key).strip()
    digest = hashlib.sha256(f"{case_id}:{salt}".encode()).hexdigest()
    return digest[:12]


def tracker_issue_url(key: str) -> str:
    return f"https://tracker.yandex.ru/{key}"


def find_pii_violations(text: str) -> list[str]:
    """Вернуть список типов найденных ПДн/запрещённых фрагментов."""
    hits: list[str] = []
    if _EMAIL_RE.search(text):
        hits.append("email")
    if _PHONE_RE.search(text):
        hits.append("phone")
    for m in _SNILS_RE.finditer(text):
        if len(re.sub(r"\D", "", m.group(0))) == 11:
            hits.append("snils")
            break
    if _UUID_RE.search(text):
        hits.append("case_uuid")
    if _CABINET_URL_RE.search(text):
        hits.append("cabinet_url")
    if _STORAGE_URL_RE.search(text):
        hits.append("storage_url")
    return hits


def sanitize_description(text: str) -> str:
    """Вырезать очевидные ПДн; остаток обрезать."""
    out = text.strip()
    out = _EMAIL_RE.sub("[email]", out)
    out = _PHONE_RE.sub("[phone]", out)
    out = _SNILS_RE.sub("[snils]", out)
    out = _UUID_RE.sub("[id]", out)
    out = _CABINET_URL_RE.sub("[cabinet-url]", out)
    out = _STORAGE_URL_RE.sub("[file-url]", out)
    return out[:3500]


def build_issue_body(
    *,
    issue_type: str,
    description: str,
    case_ref: str,
    direction: str,
    source: str,
    component: str | None,
    funnel_stage: str | None,
    channel: str | None,
    age_bucket: str | None,
    repeatability: str | None,
    correlation_id: str | None,
) -> str:
    lines = [
        f"## Тип: {ISSUE_TYPE_LABELS_RU.get(issue_type, issue_type)}",
        "",
        "## Описание (обезличено)",
        sanitize_description(description),
        "",
        "## Метаданные",
        f"- case_ref: `{case_ref}`",
        f"- direction: {direction}",
        f"- source: {source}",
    ]
    if component:
        lines.append(f"- component: {component}")
    if funnel_stage:
        lines.append(f"- funnel_stage: {funnel_stage}")
    if channel:
        lines.append(f"- channel: {channel}")
    if age_bucket:
        lines.append(f"- age_bucket: {age_bucket}")
    if repeatability:
        lines.append(f"- repeatability: {repeatability}")
    if correlation_id:
        lines.append(f"- correlation_id: `{correlation_id}`")
    lines.extend(
        [
            "",
            "## Ограничения",
            "Без ФИО, телефонов, email, СНИЛС, файлов, текста ИЛС и ссылок в кабинет.",
        ]
    )
    return "\n".join(lines)


def _headers() -> dict[str, str]:
    settings = get_settings()
    token = (settings.tracker_oauth_token or settings.tracker_token or "").strip()
    if not token:
        raise RuntimeError("TRACKER_TOKEN / YANDEX_TRACKER_OAUTH_TOKEN not configured")
    headers = {
        "Authorization": f"OAuth {token}",
        "Content-Type": "application/json",
    }
    cloud = (settings.tracker_cloud_org_id or "").strip()
    org = (settings.tracker_org_id or "").strip()
    if cloud:
        headers["X-Cloud-Org-ID"] = cloud
    elif org:
        headers["X-Org-ID"] = org
    else:
        raise RuntimeError("TRACKER_ORG_ID or TRACKER_CLOUD_ORG_ID required")
    return headers


def tracker_configured() -> bool:
    settings = get_settings()
    if not settings.tracker_enabled:
        return False
    token = (settings.tracker_oauth_token or settings.tracker_token or "").strip()
    org = (settings.tracker_org_id or settings.tracker_cloud_org_id or "").strip()
    return bool(token and org)


def health_check() -> dict[str, Any]:
    """Проверка доступности API (без токена в ответе)."""
    if not tracker_configured():
        return {"ok": False, "configured": False, "reason": "not_configured"}
    settings = get_settings()
    queue = (settings.tracker_queue or "STAZH").strip()
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(f"{API_BASE}/queues/{queue}", headers=_headers())
        return {
            "ok": resp.status_code == 200,
            "configured": True,
            "queue": queue,
            "status_code": resp.status_code,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("tracker_health_failed err=%s", type(exc).__name__)
        return {
            "ok": False,
            "configured": True,
            "queue": queue,
            "error": type(exc).__name__,
        }


def create_issue(
    *,
    summary: str,
    description: str,
    tags: list[str],
    priority: str = "normal",
    queue: str | None = None,
) -> dict[str, Any]:
    """Создать задачу в Tracker. Токен не логируется."""
    settings = get_settings()
    q = (queue or settings.tracker_queue or "STAZH").strip()
    body = {
        "queue": q,
        "summary": summary[:250],
        "description": description,
        "type": "task",
        "priority": PRIORITY_TO_TRACKER.get(priority, "normal"),
        "tags": tags[:20],
    }
    last_err: dict[str, Any] | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(f"{API_BASE}/issues/", headers=_headers(), json=body)
            data: Any
            try:
                data = resp.json() if resp.content else {}
            except Exception:  # noqa: BLE001
                data = {"text": (resp.text or "")[:200]}
            if resp.status_code in (200, 201) and isinstance(data, dict) and data.get("key"):
                key = str(data["key"])
                return {
                    "ok": True,
                    "key": key,
                    "url": tracker_issue_url(key),
                    "id": data.get("id"),
                }
            last_err = {
                "ok": False,
                "status_code": resp.status_code,
                "error": "tracker_create_failed",
                "detail": _safe_error_detail(data),
            }
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(0.4 * (2**attempt))
                continue
            return last_err
        except Exception as exc:  # noqa: BLE001
            last_err = {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
            time.sleep(0.4 * (2**attempt))
    return last_err or {"ok": False, "error": "tracker_create_failed"}


def _safe_error_detail(data: Any) -> str:
    if isinstance(data, dict):
        msgs = data.get("errorMessages") or data.get("errors") or data.get("error")
        return str(msgs)[:300]
    return str(data)[:300]


def tags_for_issue(
    *,
    issue_type: str,
    direction: str,
    source: str,
    channel: str | None,
    repeatability: str | None,
) -> list[str]:
    tags = [f"type:{issue_type}", f"dir:{direction}", f"src:{source}", "quality", "stazh"]
    if channel:
        tags.append(f"ch:{channel}")
    if repeatability and repeatability != "once":
        tags.append(f"rep:{repeatability}")
    return tags


def summary_for_issue(*, issue_type: str, case_ref: str, title_hint: str | None) -> str:
    label = ISSUE_TYPE_LABELS_RU.get(issue_type, issue_type)
    hint = (title_hint or "").strip()
    if hint:
        hint = sanitize_description(hint).split("\n")[0][:80]
        return f"[{label}] {hint} · {case_ref}"
    return f"[{label}] case_ref={case_ref}"
