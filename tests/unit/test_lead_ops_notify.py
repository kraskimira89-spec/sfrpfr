"""Уведомления о заявках: email + MAX."""

from __future__ import annotations

from sfrfr.services.lead_ops_notify import build_lead_notify_text, notify_ops_new_lead


def test_build_lead_notify_text_includes_phone_email_and_staff_chat_url() -> None:
    subject, body, staff_url = build_lead_notify_text(
        case_id="00000000-0000-4000-8000-000000000001",
        full_name="Иван Иванов",
        phone="+79001234567",
        email="client@example.com",
        channel="web_cabinet",
        source_label="с сайта",
    )
    assert "заявка" in subject.lower()
    assert "Телефон: +79001234567" in body
    assert "Email: client@example.com" in body
    assert "Дело:" in body
    assert staff_url and "focus=chat" in staff_url
    assert "/c/" in staff_url
    assert "view=cases" in staff_url
    assert "amoCRM" not in body


def test_notify_ops_skips_pytest_and_missing_case(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    result = notify_ops_new_lead(
        case_id="d0491474-8618-4615-bfe6-993f645ad740",
        full_name="MAX 11",
        channel="max_chat",
        source_label="из чата MAX",
        max_user_id="11",
    )
    assert result.get("skipped")
    get_settings.cache_clear()
