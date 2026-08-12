"""Яндекс Диск — операционные шаблоны (не ПДн). ПДн-сканы → Supabase Storage."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_workspace.oauth import oauth_headers, token_available

_DISK_API = "https://cloud-api.yandex.net/v1/disk"
# Только обезличенные ops-файлы / шаблоны заявлений.
OPS_FOLDER = "disk:/SFRFR-ops"
# Еженедельный контроль воронки MAX (без ПДн) — см. docs/marketing-sales/reports/
OPS_MARKETING_MAX_FUNNEL = f"{OPS_FOLDER}/marketing-max-funnel"
_FORBIDDEN_MARKERS = (
    "снилс",
    "snils",
    "паспорт",
    "passport",
    "ils",
    "илс",
    "трудов",
    "case-",
    "cases/",
)


def _enabled() -> tuple[bool, dict[str, Any] | None]:
    settings = get_settings()
    if not settings.yandex_disk_enabled:
        return False, {
            "ok": False,
            "skipped": True,
            "reason": "YANDEX_DISK_ENABLED=false",
            "policy": "ПДн-сканы только в Supabase Storage (ТЗ-14)",
        }
    if not token_available():
        return False, {
            "ok": False,
            "skipped": True,
            "reason": "no YANDEX_OAUTH_ACCESS_TOKEN",
        }
    return True, None


def _path_allowed(path: str) -> bool:
    normalized = (path or "").strip().lower()
    if not normalized.startswith("disk:/sfrfr-ops"):
        return False
    return not any(marker in normalized for marker in _FORBIDDEN_MARKERS)


def disk_status() -> dict[str, Any]:
    ok, skipped = _enabled()
    if not ok and skipped:
        return skipped
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(f"{_DISK_API}/", headers=oauth_headers())
        if response.status_code >= 400:
            return {
                "ok": False,
                "status_code": response.status_code,
                "detail": (response.text or "")[:300],
            }
        body = response.json() if response.content else {}
        user = body.get("user") or {}
        return {
            "ok": True,
            "used_space": body.get("used_space"),
            "total_space": body.get("total_space"),
            "login": user.get("login"),
            "ops_folder": OPS_FOLDER,
            "policy": "только SFRFR-ops; без ПДн-сканов",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


def ensure_ops_folder() -> dict[str, Any]:
    """Создать disk:/SFRFR-ops при отсутствии."""
    return ensure_ops_path(OPS_FOLDER)


def ensure_ops_path(path: str) -> dict[str, Any]:
    """Создать папку на Диске внутри SFRFR-ops (без ПДн в пути)."""
    ok, skipped = _enabled()
    if not ok and skipped:
        return skipped
    target = (path or "").strip()
    if not _path_allowed(target):
        return {"ok": False, "error": "path_forbidden_by_pdn_policy", "path": target}
    try:
        with httpx.Client(timeout=20.0) as client:
            existing = client.get(
                f"{_DISK_API}/resources",
                params={"path": target},
                headers=oauth_headers(),
            )
            if existing.status_code == 200:
                return {"ok": True, "exists": True, "path": target}
            created = client.put(
                f"{_DISK_API}/resources",
                params={"path": target},
                headers=oauth_headers(),
            )
        if created.status_code in (200, 201):
            return {"ok": True, "created": True, "path": target}
        if created.status_code == 409:
            return {"ok": True, "exists": True, "path": target}
        return {
            "ok": False,
            "status_code": created.status_code,
            "detail": (created.text or "")[:300],
            "path": target,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


def list_ops(*, path: str | None = None, limit: int = 50) -> dict[str, Any]:
    ok, skipped = _enabled()
    if not ok and skipped:
        return skipped
    target = (path or OPS_FOLDER).strip()
    if not _path_allowed(target):
        return {"ok": False, "error": "path_forbidden_by_pdn_policy", "path": target}
    ensure = ensure_ops_path(target)
    if not ensure.get("ok"):
        return ensure
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{_DISK_API}/resources",
                params={"path": target, "limit": max(1, min(limit, 100))},
                headers=oauth_headers(),
            )
        if response.status_code >= 400:
            return {
                "ok": False,
                "status_code": response.status_code,
                "detail": (response.text or "")[:300],
            }
        body = response.json() if response.content else {}
        items = ((body.get("_embedded") or {}).get("items") or [])
        return {
            "ok": True,
            "path": target,
            "count": len(items),
            "items": [
                {
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "path": item.get("path"),
                    "size": item.get("size"),
                }
                for item in items
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


def upload_ops_file(
    *,
    remote_name: str,
    content: bytes,
    overwrite: bool = False,
    folder: str | None = None,
) -> dict[str, Any]:
    """Загрузить файл только в SFRFR-ops или подпапку (без ПДн в имени/пути)."""
    ok, skipped = _enabled()
    if not ok and skipped:
        return skipped
    name = (remote_name or "").strip().lstrip("/")
    if not name or "/" in name or "\\" in name or ".." in name:
        return {"ok": False, "error": "invalid_remote_name"}
    base = (folder or OPS_FOLDER).strip().rstrip("/")
    if not _path_allowed(base):
        return {"ok": False, "error": "path_forbidden_by_pdn_policy", "path": base}
    path = f"{base}/{name}"
    if not _path_allowed(path):
        return {"ok": False, "error": "path_forbidden_by_pdn_policy", "path": path}
    ensure_root = ensure_ops_folder()
    if not ensure_root.get("ok"):
        return ensure_root
    ensure = ensure_ops_path(base)
    if not ensure.get("ok"):
        return ensure
    try:
        with httpx.Client(timeout=60.0) as client:
            href_resp = client.get(
                f"{_DISK_API}/resources/upload",
                params={"path": path, "overwrite": "true" if overwrite else "false"},
                headers=oauth_headers(),
            )
            if href_resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": href_resp.status_code,
                    "detail": (href_resp.text or "")[:300],
                }
            href = (href_resp.json() or {}).get("href")
            if not href:
                return {
                    "ok": False,
                    "error": "no_upload_href",
                    "detail": (href_resp.text or "")[:200],
                }
            put = client.put(href, content=content)
        if put.status_code in (200, 201, 202):
            return {"ok": True, "path": path, "status_code": put.status_code}
        return {
            "ok": False,
            "status_code": put.status_code,
            "detail": (put.text or "")[:300],
            "path": path,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


def encode_path(path: str) -> str:
    """Для отладки/логов — безопасный quote пути."""
    return quote(path, safe=":/")
