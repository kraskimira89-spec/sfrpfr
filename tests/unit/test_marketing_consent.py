"""Unit-тесты политики marketing consent."""

from __future__ import annotations

from sfrfr.services.marketing_consent import (
    can_send_marketing,
    classify_template,
    gate_outbound_message,
    is_stop_command,
    latest_status,
)


def test_classify_template_prefixes() -> None:
    assert classify_template("marketing_weekly") == "marketing"
    assert classify_template("promo_diag") == "marketing"
    assert classify_template("checklist_ils") == "service"
    assert classify_template("service_reminder") == "service"
    assert classify_template(None) == "service"
    assert classify_template("x", kind="mixed") == "mixed"


def test_can_send_requires_granted() -> None:
    assert can_send_marketing([], channel="max").allowed is False
    rows = [{"channel": "max", "status": "granted", "created_at": "2026-08-23"}]
    assert can_send_marketing(rows, channel="max").allowed is True
    rows2 = [
        {"channel": "max", "status": "revoked", "created_at": "2026-08-24"},
        {"channel": "max", "status": "granted", "created_at": "2026-08-23"},
    ]
    assert latest_status(rows2, channel="max") == "revoked"
    assert can_send_marketing(rows2, channel="max").allowed is False


def test_gate_service_always_ok() -> None:
    g = gate_outbound_message([], channel="max", template_code="checklist_ils_d6")
    assert g.allowed is True
    assert g.reason == "service_message"


def test_gate_marketing_blocked() -> None:
    g = gate_outbound_message([], channel="max", template_code="marketing_tips")
    assert g.allowed is False
    assert g.reason == "marketing_consent_missing"


def test_gate_mixed_blocked() -> None:
    g = gate_outbound_message([], channel="max", message_kind="mixed")
    assert g.allowed is False


def test_max_consent_does_not_cover_email() -> None:
    rows = [{"channel": "max", "status": "granted"}]
    assert can_send_marketing(rows, channel="max").allowed is True
    assert can_send_marketing(rows, channel="email").allowed is False


def test_stop_command() -> None:
    assert is_stop_command("СТОП")
    assert is_stop_command("stop")
    assert is_stop_command("Отписаться")
    assert not is_stop_command("стоп пожалуйста завтра")
