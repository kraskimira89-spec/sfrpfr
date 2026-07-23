"""Юнит-тесты Sheets / ЮKassa / security helpers (ТЗ-06)."""

from __future__ import annotations

from sfrfr.integrations.payments import YooKassaClient
from sfrfr.integrations.sheets import SheetsExporter, rows_to_values
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
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    result = SheetsExporter().push([{"case_id": "1", "segment": "b2c"}])
    assert result.get("skipped") is True
    get_settings.cache_clear()


def test_rows_to_values_header_and_order() -> None:
    matrix = rows_to_values([{"case_id": "c1", "segment": "b2c", "extra_pii": "no"}])
    assert matrix[0][0] == "case_id"
    assert matrix[1][0] == "c1"
    assert matrix[1][1] == "b2c"


def test_sheets_api_push_mocked(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "sheet123")
    monkeypatch.setenv("GOOGLE_SHEETS_WORKSHEET", "Analytics")
    monkeypatch.setenv(
        "GOOGLE_SHEETS_CREDENTIALS_JSON",
        '{"type":"service_account","client_email":"sa@x.iam.gserviceaccount.com"}',
    )
    monkeypatch.setenv("GOOGLE_SHEETS_WEBHOOK_URL", "")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        "sfrfr.integrations.sheets._load_service_account_info",
        lambda _raw: {"type": "service_account"},
    )
    monkeypatch.setattr("sfrfr.integrations.sheets._access_token", lambda _info: "tok")

    class _Resp:
        def __init__(self, code: int = 200, payload: dict | None = None) -> None:
            self.status_code = code
            self.text = "ok"
            self._payload = payload or {"updatedCells": 17}

        def json(self) -> dict:
            return self._payload

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, url, **kwargs):
            assert ":clear" in url
            return _Resp(200)

        def put(self, url, **kwargs):
            assert "valueInputOption=USER_ENTERED" in url
            assert kwargs["json"]["values"][0][0] == "case_id"
            return _Resp(200)

    monkeypatch.setattr("sfrfr.integrations.sheets.httpx.Client", _Client)
    result = SheetsExporter().push([{"case_id": "1", "segment": "b2c"}])
    assert result["ok"] is True
    assert result["transport"] == "api"
    assert result["updated_cells"] == 17
    get_settings.cache_clear()


def test_signed_ttl_constant() -> None:
    assert SIGNED_URL_TTL_SECONDS == 60
