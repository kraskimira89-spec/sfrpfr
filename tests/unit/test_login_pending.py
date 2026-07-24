"""Тесты pending-входа через MAX (ПК ждёт подтверждение)."""

from sfrfr.security.login_otp import confirm_web_login_message
from sfrfr.security.login_pending import (
    approve,
    bind_max_by_code,
    bind_max_direct,
    callback_payload_for,
    create_pending,
    get_pending,
    manager_callback_payload_for,
    mark_pending_manager,
    parse_confirm_callback,
    parse_manager_callback,
)


def test_create_and_pair_then_approve() -> None:
    pending = create_pending()
    assert pending.status == "pending_pair"
    assert len(pending.pair_code) == 6

    bound = bind_max_by_code(
        pair_code=pending.pair_code,
        max_user_id="6407832",
        contact="max_6407832@clients.sfrfr.local",
    )
    assert bound is not None
    assert bound.status == "pending_confirm"
    assert bound.max_user_id == "6407832"

    ok = approve(
        ticket_id=pending.ticket_id,
        token_hash="hash123",
        email="max_6407832@clients.sfrfr.local",
    )
    assert ok is not None
    assert ok.status == "approved"
    polled = get_pending(pending.ticket_id)
    assert polled is not None
    assert polled.token_hash == "hash123"


def test_staff_needs_manager_before_approve() -> None:
    pending = create_pending(audience="staff", staff_email="op@example.com")
    assert pending.audience == "staff"
    bound = bind_max_by_code(
        pair_code=pending.pair_code,
        max_user_id="111",
        contact="op@example.com",
    )
    assert bound is not None
    assert bound.status == "pending_confirm"
    waiting = mark_pending_manager(ticket_id=pending.ticket_id)
    assert waiting is not None
    assert waiting.status == "pending_manager"
    ok = approve(ticket_id=pending.ticket_id, token_hash="hash-staff", email="op@example.com")
    assert ok is not None
    assert ok.status == "approved"


def test_staff_trusted_can_approve_from_confirm() -> None:
    """После доверия руководитель не нужен: approve из pending_confirm."""
    pending = create_pending(audience="staff", staff_email="op2@example.com")
    bind_max_by_code(
        pair_code=pending.pair_code,
        max_user_id="222",
        contact="op2@example.com",
    )
    ok = approve(ticket_id=pending.ticket_id, token_hash="trusted", email="op2@example.com")
    assert ok is not None
    assert ok.status == "approved"


def test_bind_direct_skips_pair() -> None:
    pending = create_pending()
    bound = bind_max_direct(
        ticket_id=pending.ticket_id,
        max_user_id="99",
        contact="a@b.c",
    )
    assert bound is not None
    assert bound.status == "pending_confirm"


def test_callback_payload_roundtrip() -> None:
    assert parse_confirm_callback("confirm_web_login") == ""
    assert parse_confirm_callback(callback_payload_for("abc")) == "abc"
    assert parse_confirm_callback("other") is None
    assert parse_manager_callback(manager_callback_payload_for("tid1")) == "tid1"
    assert parse_manager_callback("confirm_web_login|x") is None


def test_confirm_message_is_pc_oriented() -> None:
    text = confirm_web_login_message()
    assert "компьютер" in text.lower()
    assert "Подтвердить вход" in text
