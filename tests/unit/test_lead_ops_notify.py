"""Уведомления о заявках: email + MAX."""

from __future__ import annotations

from sfrfr.services.lead_ops_notify import build_lead_notify_text


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
    assert "amoCRM" not in body
