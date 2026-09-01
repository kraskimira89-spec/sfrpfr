"""OAuth-заголовки и загрузка secrets для Яндекс Workspace (ТЗ-14)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from sfrfr.core.config import get_settings

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_SECRETS = _REPO_ROOT / "secrets" / "yandex-workspace.env"
_DEFAULT_DOTENV = _REPO_ROOT / ".env"
_loaded = False


def _merge_yandex_env_file(path: Path) -> None:
    """Подмешать YANDEX_* из файла в os.environ, не перезаписывая уже заданные."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key.startswith("YANDEX_"):
            continue
        if key not in os.environ:
            os.environ[key] = value


def load_workspace_secrets(*, path: Path | None = None) -> Path | None:
    """Загрузить YANDEX_* из .env, затем secrets/ (secrets не перекрывает .env/environ)."""
    global _loaded
    # Сначала .env проекта — приоритетнее устаревшего secrets на VPS.
    _merge_yandex_env_file(_DEFAULT_DOTENV)
    secrets_path = path or _DEFAULT_SECRETS
    _merge_yandex_env_file(secrets_path)
    get_settings.cache_clear()
    _loaded = True
    if secrets_path.is_file():
        return secrets_path
    if _DEFAULT_DOTENV.is_file():
        return _DEFAULT_DOTENV
    return None


def _ensure_loaded() -> None:
    if not _loaded:
        load_workspace_secrets()


def oauth_headers(*, token: str | None = None) -> dict[str, str]:
    _ensure_loaded()
    settings = get_settings()
    access = (token if token is not None else settings.yandex_oauth_access_token) or ""
    access = access.strip()
    return {
        "Authorization": f"OAuth {access}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def telemost_token() -> str:
    """Токен SFRFR_telemost; при client_id Телемост общий Workspace-токен не подставляем."""
    _ensure_loaded()
    settings = get_settings()
    dedicated = (settings.yandex_telemost_oauth_access_token or "").strip()
    telemost_client = (settings.yandex_telemost_oauth_client_id or "").strip()
    if dedicated:
        return dedicated
    if telemost_client:
        return ""
    return (settings.yandex_oauth_access_token or "").strip()


def token_available() -> bool:
    _ensure_loaded()
    return bool((get_settings().yandex_oauth_access_token or "").strip())


def telemost_token_available() -> bool:
    return bool(telemost_token())


def workspace_email() -> str:
    _ensure_loaded()
    return (get_settings().yandex_workspace_email or "proverkastaza@yandex.ru").strip()


def ping() -> dict[str, Any]:
    """Проверка токена через login.yandex.ru/info."""
    if not token_available():
        return {"ok": False, "skipped": True, "reason": "no YANDEX_OAUTH_ACCESS_TOKEN"}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                "https://login.yandex.ru/info",
                params={"format": "json"},
                headers=oauth_headers(),
            )
        if response.status_code >= 400:
            return {
                "ok": False,
                "status_code": response.status_code,
                "detail": (response.text or "")[:200],
            }
        body = response.json() if response.content else {}
        return {
            "ok": True,
            "login": body.get("login"),
            "id": body.get("id"),
            "default_email": body.get("default_email") or body.get("emails"),
            "workspace_email": workspace_email(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
