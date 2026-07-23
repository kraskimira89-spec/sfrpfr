"""Интеграционные проверки ТЗ-06: RLS-семантика, Storage, Sheets без ПДн."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from sfrfr.db.case_repository import CaseRepository
from sfrfr.integrations.payments import parse_yookassa_event
from sfrfr.integrations.sheets import SHEETS_WHITELIST, assert_anonymized_row, sanitize_rows
from sfrfr.integrations.taganay import TaganayClient
from sfrfr.security.auth import Principal
from sfrfr.security.integrations import (
    PRIVATE_STORAGE_BUCKET,
    SIGNED_URL_TTL_SECONDS,
    assert_frontend_env_has_no_service_role,
    check_cabinet_env_examples,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_signed_url_ttl_is_short() -> None:
    assert SIGNED_URL_TTL_SECONDS <= 120
    assert SIGNED_URL_TTL_SECONDS == 60


def test_storage_bucket_is_private_in_migration() -> None:
    sql = (REPO_ROOT / "supabase/migrations/20260722122128_b2c_schema_rls.sql").read_text(
        encoding="utf-8"
    )
    assert PRIVATE_STORAGE_BUCKET == "pension-docs"
    assert "pension-docs" in sql
    assert "can_access_case" in sql
    block = sql[
        sql.index("insert into storage.buckets") : sql.index("create policy pension_docs_select")
    ]
    assert "false" in block
    # Открытый public=true для bucket запрещён
    assert "true" not in block.split("allowed_mime_types")[0]


def test_sheets_rejects_pii_keys() -> None:
    with pytest.raises(ValueError, match="PII"):
        assert_anonymized_row({"case_id": "x", "full_name": "Иванов"})
    with pytest.raises(ValueError, match="PII"):
        assert_anonymized_row({"phone": "+7900"})
    with pytest.raises(ValueError, match="PII"):
        assert_anonymized_row({"ocr_text": "..."})


def test_sheets_sanitize_strips_extra() -> None:
    rows = sanitize_rows(
        [
            {
                "case_id": "1",
                "segment": "b2c",
                "region_bucket": "ural",
                "stage": "lead",
                "pipeline": "intake",
                "problem_type": "underpay",
                "created_at": "2026-01-01",
                "paid_diag": False,
                "paid_service": False,
                "result_band": "unknown",
                "sf_due": False,
                "sf_paid": False,
                "silent_flag": False,
                "preferred_channel": "web",
                "max_linked": False,
                "web_linked": True,
                "extra_noise": "drop-me",
            }
        ]
    )
    assert set(rows[0]) <= SHEETS_WHITELIST
    assert "extra_noise" not in rows[0]


def test_frontend_env_examples_have_no_service_role() -> None:
    errors = check_cabinet_env_examples(REPO_ROOT)
    assert errors == []
    with pytest.raises(AssertionError):
        assert_frontend_env_has_no_service_role(
            "NEXT_PUBLIC_SUPABASE_URL=x\nSUPABASE_SERVICE_ROLE_KEY=secret\n"
        )


def test_require_case_hides_foreign_case() -> None:
    """Семантика RLS на сервере: чужое дело → 404, не 403."""

    class _Repo(CaseRepository):
        def __init__(self) -> None:
            self.client = None  # type: ignore[assignment]

        def _case(self, case_id: str):  # type: ignore[no-untyped-def,override]
            return {
                "id": case_id,
                "client_id": "other-client",
                "expert_user_id": None,
            }

        def can_access(self, principal, case):  # type: ignore[no-untyped-def,override]
            return False

    repo = _Repo()
    principal = Principal(user_id="user-a", role=None, email="a@t.ru")
    with pytest.raises(HTTPException) as exc:
        repo.require_case(principal, "case-1")
    assert exc.value.status_code == 404


def test_yookassa_event_parse() -> None:
    parsed = parse_yookassa_event(
        {
            "event": "payment.succeeded",
            "object": {
                "id": "pay_1",
                "status": "succeeded",
                "paid": True,
                "amount": {"value": "3000.00"},
                "metadata": {"order_id": "ord", "case_id": "cas"},
            },
        }
    )
    assert parsed["provider_payment_id"] == "pay_1"
    assert parsed["paid"] is True
    assert parsed["order_id"] == "ord"


def test_taganay_payload_excludes_files(monkeypatch) -> None:
    captured: dict = {}

    class _Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"ok": True}

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr("sfrfr.integrations.taganay.httpx.Client", _Client)
    client = TaganayClient(webhook_url="https://example.test/hook", api_token="t")
    result = client.sync_case(
        case_id="c1",
        b2c_status="lead",
        pipeline_status="intake",
        full_name="Иван",
        phone="+7900",
    )
    assert result["ok"] is True
    body = captured["json"]
    assert body["case_id"] == "c1"
    assert "ocr" not in body
    assert "storage_path" not in body
    assert "findings" not in body
