"""Google Sheets: только обезличенный whitelist (ТЗ-06).

Приоритет транспорта:
1) Service Account + Spreadsheet ID (Sheets API v4)
2) Apps Script / webhook URL (fallback)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from sfrfr.core.config import get_settings

# Whitelist journey §6 + каналы (без ФИО/телефона/СНИЛС/OCR/файлов).
# Порядок колонок в таблице — стабильный.
SHEETS_COLUMNS: tuple[str, ...] = (
    "case_id",
    "segment",
    "region_bucket",
    "stage",
    "pipeline",
    "problem_type",
    "created_at",
    "paid_diag",
    "paid_service",
    "result_band",
    "sf_due",
    "sf_paid",
    "silent_flag",
    "preferred_channel",
    "max_linked",
    "web_linked",
)
SHEETS_WHITELIST: frozenset[str] = frozenset(SHEETS_COLUMNS)

_FORBIDDEN_SUBSTRINGS = (
    "full_name",
    "fio",
    "phone",
    "email",
    "snils",
    "passport",
    "ocr",
    "storage_path",
    "signed",
    "document_text",
    "max_user_id",  # сырой id мессенджера не в Sheets
)

_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"


def assert_anonymized_row(row: dict[str, Any]) -> dict[str, Any]:
    """Оставить только whitelist; упасть при запрещённых ключах."""
    lowered = {str(k).lower() for k in row}
    for key in lowered:
        for bad in _FORBIDDEN_SUBSTRINGS:
            if bad in key and key not in SHEETS_WHITELIST:
                raise ValueError(f"PII-like field forbidden in Sheets export: {key}")
    return {k: row[k] for k in SHEETS_WHITELIST if k in row}


def sanitize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [assert_anonymized_row(row) for row in rows]


def rows_to_values(rows: list[dict[str, Any]]) -> list[list[Any]]:
    """Матрица для Sheets API: заголовок + строки в фиксированном порядке колонок."""
    header = list(SHEETS_COLUMNS)
    body: list[list[Any]] = [header]
    for row in rows:
        body.append([_cell(row.get(col)) for col in SHEETS_COLUMNS])
    return body


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    return value


def _load_service_account_info(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        return {}
    path = Path(text)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(text)


def _access_token(credentials_info: dict[str, Any]) -> str:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Установите google-auth: pip install 'google-auth>=2.35.0'"
        ) from exc

    creds = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=[_SHEETS_SCOPE],
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Google service account: empty access token")
    return str(creds.token)


class SheetsExporter:
    """Выгрузка обезличенных строк в Google Sheets (API или webhook)."""

    def __init__(
        self,
        *,
        webhook_url: str | None = None,
        spreadsheet_id: str | None = None,
        worksheet: str | None = None,
        credentials_json: str | None = None,
    ) -> None:
        settings = get_settings()
        raw_hook = (
            webhook_url if webhook_url is not None else settings.google_sheets_webhook_url
        )
        self.webhook_url = raw_hook.rstrip("/") if raw_hook else ""
        self.spreadsheet_id = (
            spreadsheet_id
            if spreadsheet_id is not None
            else settings.google_sheets_spreadsheet_id
        ).strip()
        self.worksheet = (
            worksheet if worksheet is not None else settings.google_sheets_worksheet
        ).strip() or "Analytics"
        cred_raw = (
            credentials_json
            if credentials_json is not None
            else settings.google_sheets_credentials_json
        )
        self._credentials_raw = (cred_raw or "").strip()

    @property
    def api_configured(self) -> bool:
        return bool(self.spreadsheet_id and self._credentials_raw)

    @property
    def available(self) -> bool:
        return self.api_configured or bool(self.webhook_url)

    def push(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        clean = sanitize_rows(rows)
        if self.api_configured:
            return self._push_api(clean)
        if self.webhook_url:
            return self._push_webhook(clean)
        return {
            "ok": False,
            "skipped": True,
            "reason": "no GOOGLE_SHEETS credentials (API or WEBHOOK_URL)",
            "rows": len(clean),
        }

    def _push_api(self, clean: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            info = _load_service_account_info(self._credentials_raw)
            token = _access_token(info)
            values = rows_to_values(clean)
            range_a1 = quote(f"'{self.worksheet}'!A1", safe="")
            clear_range = quote(f"'{self.worksheet}'!A:Z", safe="")
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            clear_url = f"{_SHEETS_API}/{self.spreadsheet_id}/values/{clear_range}:clear"
            update_url = (
                f"{_SHEETS_API}/{self.spreadsheet_id}/values/{range_a1}"
                f"?valueInputOption=USER_ENTERED"
            )
            with httpx.Client(timeout=45.0) as client:
                clear_resp = client.post(clear_url, headers=headers, json={})
                if clear_resp.status_code >= 400:
                    return {
                        "ok": False,
                        "transport": "api",
                        "status_code": clear_resp.status_code,
                        "error": clear_resp.text[:500],
                        "rows": len(clean),
                    }
                update_resp = client.put(
                    update_url,
                    headers=headers,
                    json={"values": values},
                )
            return {
                "ok": 200 <= update_resp.status_code < 300,
                "transport": "api",
                "status_code": update_resp.status_code,
                "rows": len(clean),
                "updated_cells": (update_resp.json() or {}).get("updatedCells")
                if update_resp.status_code < 300
                else None,
                "error": None
                if update_resp.status_code < 300
                else update_resp.text[:500],
            }
        except Exception as exc:  # noqa: BLE001 - analytics не блокирует дела
            return {
                "ok": False,
                "transport": "api",
                "error": f"{type(exc).__name__}: {exc}",
                "rows": len(clean),
            }

    def _push_webhook(self, clean: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.webhook_url,
                    json={"rows": clean, "source": "sfrfr", "pii": False},
                    headers={"Content-Type": "application/json"},
                )
            return {
                "ok": 200 <= response.status_code < 300,
                "transport": "webhook",
                "status_code": response.status_code,
                "rows": len(clean),
            }
        except Exception as exc:  # noqa: BLE001 - analytics не блокирует дела
            return {
                "ok": False,
                "transport": "webhook",
                "error": type(exc).__name__,
                "rows": len(clean),
            }
