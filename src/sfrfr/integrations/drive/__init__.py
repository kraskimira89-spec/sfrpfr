"""Google Drive: service account (без ПДн в логах/ответах CLI).

Ключ: GOOGLE_DRIVE_CREDENTIALS_JSON (путь к SA JSON или JSON строкой).
Файлы/папки нужно расшарить на email SA (client_email в JSON).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from sfrfr.core.config import get_settings

_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
_DRIVE_API = "https://www.googleapis.com/drive/v3"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def load_service_account_info(raw: str) -> dict[str, Any]:
    text = raw.strip().strip('"').strip("'")
    if not text:
        raise ValueError("GOOGLE_DRIVE_CREDENTIALS_JSON пуст")

    candidates = [Path(text)]
    if not Path(text).is_absolute():
        candidates.append(_repo_root() / text)
        candidates.append(Path.cwd() / text)

    for path in candidates:
        if path.is_file():
            payload = path.read_text(encoding="utf-8").strip()
            if not payload:
                raise ValueError(f"пустой файл ключа: {path}")
            return json.loads(payload)

    if text.startswith("{"):
        return json.loads(text)

    raise FileNotFoundError(
        "JSON ключ Google Drive SA не найден. Проверьте GOOGLE_DRIVE_CREDENTIALS_JSON="
        f"{text!r} (искали: {', '.join(str(p) for p in candidates)})"
    )


def _access_token(credentials_info: dict[str, Any], *, scopes: list[str] | None = None) -> str:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Установите google-auth: pip install 'google-auth>=2.35.0'"
        ) from exc

    creds = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=scopes or [_DRIVE_SCOPE],
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Google Drive SA: empty access token")
    return str(creds.token)


class DriveClient:
    """Минимальный клиент Drive API v3 (list)."""

    def __init__(self, *, credentials_json: str | None = None) -> None:
        settings = get_settings()
        raw = (
            credentials_json
            if credentials_json is not None
            else settings.google_drive_credentials_json
        )
        self._credentials_raw = (raw or "").strip()
        self.folder_id = (settings.google_drive_folder_id or "").strip()

    @property
    def available(self) -> bool:
        return bool(self._credentials_raw)

    def list_files(self, *, page_size: int = 10, folder_id: str | None = None) -> dict[str, Any]:
        if not self.available:
            return {
                "ok": False,
                "skipped": True,
                "reason": "no GOOGLE_DRIVE_CREDENTIALS_JSON",
                "files": [],
            }
        try:
            info = load_service_account_info(self._credentials_raw)
            token = _access_token(info)
            headers = {"Authorization": f"Bearer {token}"}
            params: dict[str, str | int] = {
                "pageSize": max(1, min(page_size, 100)),
                "fields": "files(id,name,mimeType,modifiedTime),nextPageToken",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            target_folder = (folder_id if folder_id is not None else self.folder_id).strip()
            if target_folder:
                params["q"] = f"'{target_folder}' in parents and trashed=false"

            with httpx.Client(timeout=45.0) as client:
                resp = client.get(f"{_DRIVE_API}/files", headers=headers, params=params)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:500],
                    "files": [],
                    "sa_email": info.get("client_email"),
                }
            payload = resp.json() or {}
            files = payload.get("files") or []
            return {
                "ok": True,
                "status_code": resp.status_code,
                "files": [
                    {
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "mimeType": f.get("mimeType"),
                        "modifiedTime": f.get("modifiedTime"),
                    }
                    for f in files
                ],
                "count": len(files),
                "sa_email": info.get("client_email"),
                "folder_id": target_folder or None,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "files": [],
            }
