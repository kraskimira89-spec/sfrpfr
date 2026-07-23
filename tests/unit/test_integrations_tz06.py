"""Юнит-тесты Sheets / ЮKassa / security helpers (ТЗ-06)."""

from __future__ import annotations

from sfrfr.integrations.payments import YooKassaClient
from sfrfr.integrations.sheets import SheetsExporter
from sfrfr.security.integrations import SIGNED_URL_TTL_SECONDS


def test_yookassa_unavailable_without_keys(monkeypatch) -> None:
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    assert YooKassaClient().available is False
    get_settings.cache_clear()


def test_sheets_exporter_skips_without_url(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_WEBHOOK_URL", "")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    result = SheetsExporter().push([{"case_id": "1", "segment": "b2c"}])
    assert result.get("skipped") is True
    get_settings.cache_clear()


def test_signed_ttl_constant() -> None:
    assert SIGNED_URL_TTL_SECONDS == 60
