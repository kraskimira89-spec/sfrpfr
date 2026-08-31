"""Яндекс Диск: ops (SFRFR-ops, без ПДн в путях) + зеркало дел (SFRFR-cases).

Источник истины документов: Supabase Storage (кабинет) / local uploads (MAX).
Диск — best-effort зеркало: disk:/SFRFR-cases/{case_id}/.
"""

from __future__ import annotations

import re
import uuid
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
# Зеркало сканов дел (ПДн); путь только с UUID дела.
CASES_FOLDER = "disk:/SFRFR-cases"

_FORBIDDEN_OPS_MARKERS = (
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
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_SAFE_NAME = re.compile(r"[^\w.\-]+", re.UNICODE)


def _enabled() -> tuple[bool, dict[str, Any] | None]:
    settings = get_settings()
    if not settings.yandex_disk_enabled:
        return False, {
            "ok": False,
            "skipped": True,
            "reason": "YANDEX_DISK_ENABLED=false",
            "policy": "ops: SFRFR-ops; cases mirror: SFRFR-cases/{case_id}",
        }
    if not token_available():
        return False, {
            "ok": False,
            "skipped": True,
            "reason": "no YANDEX_OAUTH_ACCESS_TOKEN",
        }
    return True, None


def _path_allowed(path: str) -> bool:
    """Whitelist только SFRFR-ops (без маркеров ПДн в пути)."""
    normalized = (path or "").strip().lower()
    if not normalized.startswith("disk:/sfrfr-ops"):
        return False
    return not any(marker in normalized for marker in _FORBIDDEN_OPS_MARKERS)


def _normalize_case_id(case_id: str) -> str | None:
    raw = (case_id or "").strip()
    if not raw or not _UUID_RE.match(raw):
        return None
    return raw.lower()


def _cases_path_allowed(path: str, *, case_id: str | None = None) -> bool:
    """Whitelist disk:/SFRFR-cases или disk:/SFRFR-cases/<uuid>/…."""
    normalized = (path or "").strip().rstrip("/")
    low = normalized.lower()
    if low == "disk:/sfrfr-cases":
        return True
    prefix = "disk:/sfrfr-cases/"
    if not low.startswith(prefix):
        return False
    rest = normalized[len(prefix) :]
    if not rest or ".." in rest or "\\" in rest:
        return False
    first = rest.split("/", 1)[0]
    if not _UUID_RE.match(first):
        return False
    if case_id is not None:
        cid = _normalize_case_id(case_id)
        if not cid or first.lower() != cid:
            return False
    return True


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
            "cases_folder": CASES_FOLDER,
            "policy": "SFRFR-ops (без ПДн в путях); SFRFR-cases/{case_id} — зеркало сканов",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


def _ensure_disk_folder(target: str, *, allow_cases: bool = False) -> dict[str, Any]:
    ok, skipped = _enabled()
    if not ok and skipped:
        return skipped
    path = (target or "").strip()
    if allow_cases:
        if not _cases_path_allowed(path):
            return {"ok": False, "error": "path_forbidden_by_cases_policy", "path": path}
    elif not _path_allowed(path):
        return {"ok": False, "error": "path_forbidden_by_pdn_policy", "path": path}
    try:
        with httpx.Client(timeout=20.0) as client:
            existing = client.get(
                f"{_DISK_API}/resources",
                params={"path": path},
                headers=oauth_headers(),
            )
            if existing.status_code == 200:
                return {"ok": True, "exists": True, "path": path}
            created = client.put(
                f"{_DISK_API}/resources",
                params={"path": path},
                headers=oauth_headers(),
            )
        if created.status_code in (200, 201):
            return {"ok": True, "created": True, "path": path}
        if created.status_code == 409:
            return {"ok": True, "exists": True, "path": path}
        return {
            "ok": False,
            "status_code": created.status_code,
            "detail": (created.text or "")[:300],
            "path": path,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


def ensure_ops_folder() -> dict[str, Any]:
    """Создать disk:/SFRFR-ops при отсутствии."""
    return ensure_ops_path(OPS_FOLDER)


def ensure_ops_path(path: str) -> dict[str, Any]:
    """Создать папку на Диске внутри SFRFR-ops (без ПДн в пути)."""
    return _ensure_disk_folder(path, allow_cases=False)


def ensure_cases_folder() -> dict[str, Any]:
    """Создать disk:/SFRFR-cases при отсутствии."""
    return _ensure_disk_folder(CASES_FOLDER, allow_cases=True)


def ensure_case_folder(case_id: str) -> dict[str, Any]:
    """Создать disk:/SFRFR-cases/{case_id}."""
    cid = _normalize_case_id(case_id)
    if not cid:
        return {"ok": False, "error": "invalid_case_id"}
    root = ensure_cases_folder()
    if not root.get("ok"):
        return root
    return _ensure_disk_folder(f"{CASES_FOLDER}/{cid}", allow_cases=True)


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
    return _put_upload(path=path, content=content, overwrite=overwrite)


def _safe_remote_name(filename: str) -> str:
    cleaned = _SAFE_NAME.sub("_", (filename or "").strip()).strip("._") or "file"
    return cleaned[:180]


def upload_case_file(
    case_id: str,
    *,
    remote_name: str,
    content: bytes,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Загрузить файл в disk:/SFRFR-cases/{case_id}/."""
    ok, skipped = _enabled()
    if not ok and skipped:
        return skipped
    cid = _normalize_case_id(case_id)
    if not cid:
        return {"ok": False, "error": "invalid_case_id"}
    name = _safe_remote_name(remote_name)
    if "/" in name or "\\" in name or ".." in name:
        return {"ok": False, "error": "invalid_remote_name"}
    folder = f"{CASES_FOLDER}/{cid}"
    path = f"{folder}/{name}"
    if not _cases_path_allowed(path, case_id=cid):
        return {"ok": False, "error": "path_forbidden_by_cases_policy", "path": path}
    ensure = ensure_case_folder(cid)
    if not ensure.get("ok"):
        return ensure
    return _put_upload(path=path, content=content, overwrite=overwrite)


def mirror_case_document(case_id: str, filename: str, data: bytes) -> dict[str, Any]:
    """Best-effort зеркало: unique remote name под папкой дела."""
    cid = _normalize_case_id(case_id)
    if not cid:
        return {"ok": False, "error": "invalid_case_id", "skipped": False}
    remote = f"{uuid.uuid4().hex[:8]}_{_safe_remote_name(filename)}"
    result = upload_case_file(cid, remote_name=remote, content=data, overwrite=False)
    if result.get("ok"):
        result = {**result, "case_id": cid, "remote_name": remote}
    return result


def _put_upload(*, path: str, content: bytes, overwrite: bool) -> dict[str, Any]:
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
                    "path": path,
                }
            href = (href_resp.json() or {}).get("href")
            if not href:
                return {
                    "ok": False,
                    "error": "no_upload_href",
                    "detail": (href_resp.text or "")[:200],
                    "path": path,
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
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200], "path": path}


def encode_path(path: str) -> str:
    """Для отладки/логов — безопасный quote пути."""
    return quote(path, safe=":/")
