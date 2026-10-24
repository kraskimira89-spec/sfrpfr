"""Изолированный сквозной срез E05/F04: событие → факты → политика → текст → outbox mock."""

from __future__ import annotations

from sfrfr.services.max_outbox_guards import (
    SendPersistOutcome,
    classify_send_persist_outcome,
    may_blind_retry_after_unknown_accept,
    pre_send_still_allowed,
    reenqueue_attachments_safe,
)
from sfrfr.services.max_sfrfr110_bridge import (
    POLICY_VERSION,
    TrustedOpResult,
    assert_no_limit_claim_without_measure,
    build_e05_f04_outbound,
)


def test_f04_limit_op_failed_uncertainty_without_limit_claim() -> None:
    limit_op = TrustedOpResult(
        case_id="case-A",
        operation_id="op-limit-1",
        op_kind="apply_provisional_limit",
        ok=False,
        source="db_write_ack",
        version="v1",
        detail="update returned 0 rows",
    )
    pkg = build_e05_f04_outbound(
        case_id="case-A",
        operation_id="op-reply-1",
        confirmed_point="дате начала",
        unknown_impact_area="расчёт",
        limit_op=limit_op,
    )
    assert pkg.ok is True
    assert pkg.policy_version == POLICY_VERSION
    assert "пока не установлено" in pkg.text.casefold()
    assert assert_no_limit_claim_without_measure(pkg.text, limit_applied=False)
    assert "использование ограничено" not in pkg.text.casefold()
    assert "отмечен как требующий проверки" not in pkg.text.casefold()


def test_f04_llm_flag_not_trusted() -> None:
    limit_op = TrustedOpResult(
        case_id="case-A",
        operation_id="op-limit-2",
        op_kind="apply_provisional_limit",
        ok=True,
        source="llm_self_report",
    )
    pkg = build_e05_f04_outbound(
        case_id="case-A",
        operation_id="op-reply-2",
        confirmed_point="дате",
        unknown_impact_area="отчёт",
        limit_op=limit_op,
    )
    assert "использование ограничено" not in pkg.text.casefold()


def test_f04_wrong_case_id_not_trusted() -> None:
    limit_op = TrustedOpResult(
        case_id="case-OTHER",
        operation_id="op-limit-3",
        op_kind="apply_provisional_limit",
        ok=True,
        source="db_write_ack",
    )
    pkg = build_e05_f04_outbound(
        case_id="case-A",
        operation_id="op-reply-3",
        confirmed_point="дате",
        unknown_impact_area="проект",
        limit_op=limit_op,
    )
    assert "использование ограничено" not in pkg.text.casefold()


def test_limit_applied_allows_marked_phrase() -> None:
    limit_op = TrustedOpResult(
        case_id="case-A",
        operation_id="op-limit-4",
        op_kind="apply_provisional_limit",
        ok=True,
        source="repository_update_ok",
        version="v2",
    )
    pkg = build_e05_f04_outbound(
        case_id="case-A",
        operation_id="op-reply-4",
        confirmed_point="дате",
        unknown_impact_area="расчёт",
        limit_op=limit_op,
    )
    assert "отмечен как требующий проверки" in pkg.text.casefold()
    assert "использование ограничено" in pkg.text.casefold()
    assert any("op-limit-4" in r for r in pkg.evidence_refs)


def test_model_invented_fixed_or_limit_blocked_metric() -> None:
    pkg = build_e05_f04_outbound(
        case_id="case-A",
        operation_id="op-reply-5",
        confirmed_point="дате",
        unknown_impact_area="расчёт",
        limit_op=TrustedOpResult(
            case_id="case-A",
            operation_id="op-x",
            op_kind="apply_provisional_limit",
            ok=False,
            source="db_write_ack",
        ),
        invented_model_text=(
            "Результат отмечен как требующий проверки; использование ограничено. "
            "Всё исправлено."
        ),
    )
    assert pkg.blocked_reason == "model_invented_unconfirmed_claim"
    assert "использование ограничено" not in pkg.text.casefold()
    assert "исправлено" not in pkg.text.casefold() or "не буду сообщать" in pkg.text.casefold()


def test_slice_through_mock_outbox_and_transport() -> None:
    """handler-подобные шаги без реальной БД/MAX."""
    pkg = build_e05_f04_outbound(
        case_id="case-A",
        operation_id="op-slice",
        confirmed_point="периоде",
        unknown_impact_area="длительность",
        limit_op=TrustedOpResult(
            case_id="case-A",
            operation_id="op-lim",
            op_kind="apply_provisional_limit",
            ok=False,
            source="db_write_ack",
        ),
    )
    outbox_row = {
        "id": "ob-1",
        "case_id": pkg.case_id,
        "message_id": "msg-1",
        "body": pkg.text,
        "attachments": pkg.attachments,
        "status": "pending",
        "operation_id": pkg.operation_id,
        "policy_version": pkg.policy_version,
    }
    # pre-send ok
    gate = pre_send_still_allowed(recipient_access_ok=True)
    assert gate["send"] is True
    # mock transport accept
    transport_ok = True
    # simulate persist failure after accept
    outcome = classify_send_persist_outcome(
        transport_accepted=transport_ok,
        outbox_status_saved=False,
        case_messages_updated=False,
    )
    assert outcome == SendPersistOutcome.UNKNOWN_AFTER_ACCEPT
    assert may_blind_retry_after_unknown_accept() is False
    assert outbox_row["body"] == pkg.text
    assert "использование ограничено" not in outbox_row["body"].casefold()


def test_reenqueue_buttons_vs_stale_text() -> None:
    bad = reenqueue_attachments_safe(
        existing_body="Старое предложение этапа",
        new_body="Новый текст без offer",
        new_attachments=[{"type": "inline_keyboard"}],
    )
    assert bad["allow_attachment_update"] is False
    ok = reenqueue_attachments_safe(
        existing_body="Тот же текст",
        new_body="Тот же текст",
        new_attachments=[{"type": "inline_keyboard"}],
    )
    assert ok["allow_attachment_update"] is True


def test_offer_refused_after_enqueue_blocks_send() -> None:
    gate = pre_send_still_allowed(
        is_offer_message=True,
        offer_refused_after_enqueue=True,
    )
    assert gate["send"] is False
    assert gate["reason"] == "offer_refused_after_enqueue"
