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

# write нужен для создания папок; readonly недостаточно
_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
_FOLDER_MIME = "application/vnd.google-apps.folder"
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


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class DriveClient:
    """Минимальный клиент Drive API v3 (list / mkdir)."""

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

    def _auth(self) -> tuple[dict[str, Any], dict[str, str]]:
        info = load_service_account_info(self._credentials_raw)
        token = _access_token(info)
        return info, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def list_files(self, *, page_size: int = 10, folder_id: str | None = None) -> dict[str, Any]:
        if not self.available:
            return {
                "ok": False,
                "skipped": True,
                "reason": "no GOOGLE_DRIVE_CREDENTIALS_JSON",
                "files": [],
            }
        try:
            info, headers = self._auth()
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

    def create_folder(
        self,
        name: str,
        *,
        parent_id: str | None = None,
        exist_ok: bool = True,
    ) -> dict[str, Any]:
        """Создать папку в parent (по умолчанию GOOGLE_DRIVE_FOLDER_ID)."""
        folder_name = (name or "").strip()
        if not folder_name:
            return {"ok": False, "error": "empty folder name"}
        if not self.available:
            return {
                "ok": False,
                "skipped": True,
                "reason": "no GOOGLE_DRIVE_CREDENTIALS_JSON",
            }
        parent = (parent_id if parent_id is not None else self.folder_id).strip()
        if not parent:
            return {"ok": False, "error": "parent folder id required"}

        try:
            info, headers = self._auth()
            safe = _escape_drive_query(folder_name)
            find_q = (
                f"name='{safe}' and '{parent}' in parents "
                f"and mimeType='{_FOLDER_MIME}' and trashed=false"
            )
            with httpx.Client(timeout=45.0) as client:
                found = client.get(
                    f"{_DRIVE_API}/files",
                    headers=headers,
                    params={
                        "q": find_q,
                        "pageSize": 1,
                        "fields": "files(id,name,mimeType,webViewLink)",
                        "supportsAllDrives": "true",
                        "includeItemsFromAllDrives": "true",
                    },
                )
                if found.status_code < 300:
                    existing = (found.json() or {}).get("files") or []
                    if existing:
                        item = existing[0]
                        return {
                            "ok": True,
                            "created": False,
                            "existed": True,
                            "id": item.get("id"),
                            "name": item.get("name"),
                            "mimeType": item.get("mimeType"),
                            "webViewLink": item.get("webViewLink"),
                            "parent_id": parent,
                            "sa_email": info.get("client_email"),
                        }

                resp = client.post(
                    f"{_DRIVE_API}/files",
                    headers=headers,
                    params={
                        "supportsAllDrives": "true",
                        "fields": "id,name,mimeType,webViewLink",
                    },
                    json={
                        "name": folder_name,
                        "mimeType": _FOLDER_MIME,
                        "parents": [parent],
                    },
                )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:500],
                    "parent_id": parent,
                    "sa_email": info.get("client_email"),
                }
            body = resp.json() or {}
            return {
                "ok": True,
                "created": True,
                "existed": False,
                "id": body.get("id"),
                "name": body.get("name"),
                "mimeType": body.get("mimeType"),
                "webViewLink": body.get("webViewLink"),
                "parent_id": parent,
                "sa_email": info.get("client_email"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def rename(self, file_id: str, name: str) -> dict[str, Any]:
        """Переименовать файл/папку."""
        new_name = (name or "").strip()
        fid = (file_id or "").strip()
        if not new_name or not fid:
            return {"ok": False, "error": "file_id and name required"}
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no GOOGLE_DRIVE_CREDENTIALS_JSON"}
        try:
            info, headers = self._auth()
            with httpx.Client(timeout=45.0) as client:
                resp = client.patch(
                    f"{_DRIVE_API}/files/{fid}",
                    headers=headers,
                    params={
                        "supportsAllDrives": "true",
                        "fields": "id,name,mimeType,webViewLink",
                    },
                    json={"name": new_name},
                )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:500],
                    "sa_email": info.get("client_email"),
                }
            body = resp.json() or {}
            return {
                "ok": True,
                "id": body.get("id"),
                "name": body.get("name"),
                "webViewLink": body.get("webViewLink"),
                "sa_email": info.get("client_email"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def ensure_path(self, segments: list[str], *, parent_id: str | None = None) -> dict[str, Any]:
        """Создать цепочку папок parent/a/b/c (idempotent)."""
        current = (parent_id if parent_id is not None else self.folder_id).strip()
        if not current:
            return {"ok": False, "error": "parent folder id required"}
        created: list[dict[str, Any]] = []
        for segment in segments:
            name = (segment or "").strip()
            if not name:
                continue
            result = self.create_folder(name, parent_id=current)
            if not result.get("ok"):
                return {**result, "path_created": created}
            created.append(
                {
                    "id": result.get("id"),
                    "name": result.get("name"),
                    "created": result.get("created"),
                    "existed": result.get("existed"),
                }
            )
            current = str(result.get("id") or "")
            if not current:
                return {
                    "ok": False,
                    "error": "empty folder id after create",
                    "path_created": created,
                }
        return {
            "ok": True,
            "folder_id": current,
            "path": "/".join(s.strip() for s in segments if s.strip()),
            "nodes": created,
        }

    def ensure_workspace_tree(self, *, root_id: str | None = None) -> dict[str, Any]:
        """Создать рекомендованное дерево SFRFR в корневой папке Drive."""
        root = (root_id if root_id is not None else self.folder_id).strip()
        if not root:
            return {"ok": False, "error": "GOOGLE_DRIVE_FOLDER_ID required"}
        nodes: list[dict[str, Any]] = []
        for path in WORKSPACE_TREE_PATHS:
            result = self.ensure_path(list(path), parent_id=root)
            if not result.get("ok"):
                return {
                    "ok": False,
                    "error": result.get("error"),
                    "failed_path": "/".join(path),
                    "nodes": nodes,
                }
            nodes.append({"path": "/".join(path), "folder_id": result.get("folder_id")})
        return {"ok": True, "root_id": root, "folders": len(nodes), "nodes": nodes}

    def ensure_case_tree(
        self,
        case_id: str,
        *,
        status: str = "active",
        root_id: str | None = None,
    ) -> dict[str, Any]:
        """Папка дела только по case_id (без ФИО/СНИЛС), после согласия на ПДн."""
        cid = (case_id or "").strip()
        if not cid:
            return {"ok": False, "error": "case_id required"}
        if any(ch in cid for ch in ("/", "\\", "\n", "\r")):
            return {"ok": False, "error": "invalid case_id"}
        bucket = {
            "active": "Активные",
            "done": "Завершённые",
            "archive": "Архив_по_сроку_хранения",
        }.get((status or "active").strip().lower(), "Активные")
        root = (root_id if root_id is not None else self.folder_id).strip()
        # сначала путь до case_id, потом подпапки
        base = self.ensure_path(["02_Кейсы_клиентов", bucket, cid], parent_id=root)
        if not base.get("ok"):
            return base
        case_folder_id = str(base.get("folder_id") or "")
        children: list[dict[str, Any]] = []
        for sub in CASE_SUBFOLDERS:
            child = self.create_folder(sub, parent_id=case_folder_id)
            if not child.get("ok"):
                return {**child, "case_folder_id": case_folder_id}
            children.append({"name": sub, "id": child.get("id"), "created": child.get("created")})
        return {
            "ok": True,
            "case_id": cid,
            "status_bucket": bucket,
            "case_folder_id": case_folder_id,
            "webViewLink": f"https://drive.google.com/drive/folders/{case_folder_id}",
            "children": children,
            "note": "Сканы предпочтительно в Supabase Storage; Drive — шаблоны/обмен",
        }


# Рекомендованное дерево (пути от корня GOOGLE_DRIVE_FOLDER_ID).
WORKSPACE_TREE_PATHS: tuple[tuple[str, ...], ...] = (
    ("00_Управление", "Оферта_и_согласия"),
    ("00_Управление", "Шаблоны_договоров"),
    ("00_Управление", "Политики_и_регламенты"),
    ("01_Шаблоны_документов", "Заявления_в_СФР"),
    ("01_Шаблоны_документов", "Запросы_в_архивы"),
    ("01_Шаблоны_документов", "Сопроводительные_письма"),
    ("01_Шаблоны_документов", "Чек_листы"),
    ("02_Кейсы_клиентов", "Активные"),
    ("02_Кейсы_клиентов", "Завершённые"),
    ("02_Кейсы_клиентов", "Архив_по_сроку_хранения"),
    ("03_Обезличенная_аналитика", "Google_Sheets"),
    ("03_Обезличенная_аналитика", "Отчёты"),
    ("04_База_знаний", "Нормативные_акты"),
    ("04_База_знаний", "Разъяснения_СФР"),
    ("04_База_знаний", "Проверенные_кейсы_без_ПДн"),
    ("04_База_знаний", "FAQ"),
    ("99_Техническое", "Импорт_и_временные_файлы"),
)

CASE_SUBFOLDERS: tuple[str, ...] = (
    "01_Исходные_документы",
    "02_ИЛС_и_стаж",
    "03_Архивные_справки",
    "04_Подготовленные_документы",
    "05_Ответы_СФР_и_результат",
    "06_Договор_и_согласия",
)

ROOT_FOLDER_NAME = "SFRFR — Пенсионные дела"
