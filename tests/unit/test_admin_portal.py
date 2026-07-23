"""Тесты ролевых ограничений admin portal (ТЗ-04 + каналы ТЗ-09)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from sfrfr.api.routes import admin_portal
from sfrfr.security.auth import Principal, StaffRole


def test_require_expert_rejects_operator() -> None:
    principal = Principal(user_id="u1", email="op@example.com", role=StaffRole.OPERATOR)
    with pytest.raises(HTTPException) as exc:
        admin_portal._require_expert(principal)
    assert exc.value.status_code == 403


def test_require_expert_allows_expert_and_admin() -> None:
    expert = Principal(user_id="u2", email="ex@example.com", role=StaffRole.EXPERT)
    admin = Principal(user_id="u3", email="ad@example.com", role=StaffRole.ADMIN)
    assert admin_portal._require_expert(expert) is expert
    assert admin_portal._require_expert(admin) is admin


def _base_case() -> dict:
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "pipeline_status": "audited",
        "b2c_status": "lead",
        "clients": {
            "full_name": "Иванов",
            "phone": "+7900",
            "email": "a@b.c",
            "preferred_channel": "max_miniapp",
            "max_user_id": "max-1",
            "user_id": None,
        },
        "documents": [{"id": "d1", "storage_path": "c/d/f.pdf", "doc_type": None}],
        "checklist_items": [],
    }


def test_filter_staff_case_hides_ocr_from_operator() -> None:
    operator = Principal(user_id="op", email="o@x", role=StaffRole.OPERATOR)
    payload = admin_portal._filter_staff_case(_base_case(), operator)
    assert "findings" not in payload
    assert "ocr_texts" not in payload
    assert payload["client"]["max_user_id"] is None
    assert payload["client"]["max_linked"] is True
    assert payload["client"]["preferred_channel"] == "max_miniapp"
    assert payload["role_capabilities"]["can_edit_pipeline"] is False
    assert payload["role_capabilities"]["can_view_ocr"] is False
    assert payload["role_capabilities"]["can_manage_roles"] is False


def test_filter_staff_case_expert_sees_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = {
        "ocr_texts": ["scan"],
        "findings": [{"type": "gap", "detail": "период"}],
        "ils_periods": [],
        "labor_periods": [],
        "draft": {"title": "Заявление", "body": "..."},
        "classifications": [],
    }
    fake_client = MagicMock()
    chain = (
        fake_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    )
    chain.execute.return_value = SimpleNamespace(data=pipeline)
    monkeypatch.setattr(admin_portal, "get_supabase_client", lambda: fake_client)

    expert = Principal(user_id="ex", email="e@x", role=StaffRole.EXPERT)
    payload = admin_portal._filter_staff_case(_base_case(), expert)
    assert payload["findings"] == pipeline["findings"]
    assert payload["ocr_texts"] == ["scan"]
    assert payload["client"]["max_user_id"] == "max-1"
    assert payload["role_capabilities"]["can_edit_checklist"] is True
    assert payload["role_capabilities"]["can_confirm_result"] is True
    assert payload["role_capabilities"]["can_manage_orders"] is False
