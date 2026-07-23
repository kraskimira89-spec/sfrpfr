"""Google Sheets: только обезличенный whitelist (ТЗ-06)."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings

# Whitelist journey §6 + каналы (без ФИО/телефона/СНИЛС/OCR/файлов).
SHEETS_WHITELIST: frozenset[str] = frozenset(
    {
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
    }
)

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


def assert_anonymized_row(row: dict[str, Any]) -> dict[str, Any]:
    """Оставить только whitelist; упасть при запрещённых ключах."""
    lowered = {str(k).lower() for k in row}
    for key in lowered:
        for bad in _FORBIDDEN_SUBSTRINGS:
            if bad in key and key not in SHEETS_WHITELIST:
                raise ValueError(f"PII-like field forbidden in Sheets export: {key}")
    clean = {k: row[k] for k in SHEETS_WHITELIST if k in row}
    extra = set(row) - SHEETS_WHITELIST
    if extra:
        # тихо отбрасываем лишнее, не отправляем
        pass
    return clean


def sanitize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [assert_anonymized_row(row) for row in rows]


class SheetsExporter:
    """
    Выгрузка в Google Sheets через Apps Script / webhook URL.
    Service account JSON опционален позже; MVP — HTTPS webhook без ПДн.
    """

    def __init__(self, *, webhook_url: str | None = None) -> None:
        settings = get_settings()
        raw = webhook_url if webhook_url is not None else settings.google_sheets_webhook_url
        self.webhook_url = raw.rstrip("/") if raw else ""

    @property
    def available(self) -> bool:
        return bool(self.webhook_url)

    def push(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        clean = sanitize_rows(rows)
        if not self.available:
            return {
                "ok": False,
                "skipped": True,
                "reason": "no GOOGLE_SHEETS_WEBHOOK_URL",
                "rows": len(clean),
            }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.webhook_url,
                    json={"rows": clean, "source": "sfrfr", "pii": False},
                    headers={"Content-Type": "application/json"},
                )
            return {
                "ok": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "rows": len(clean),
            }
        except Exception as exc:  # noqa: BLE001 - analytics не блокирует дела
            return {"ok": False, "error": type(exc).__name__, "rows": len(clean)}
