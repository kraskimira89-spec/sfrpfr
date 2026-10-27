"""Этап 9: валидация отчёта о подаче (форма клиента/сотрудника)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sfrfr.services.submission_reports import (
    PROOF_MISSING_NOTE,
    SubmissionReportError,
    audit_action_for_kind,
    build_report_row,
    proof_missing_note,
    validate_submission_payload,
)


def test_confirmed_requires_date_method_what() -> None:
    with pytest.raises(SubmissionReportError):
        validate_submission_payload(
            decision="confirmed",
            submitted_on=None,
            method="gosuslugi",
            submitted_what="Пакет обращений",
            source="client_self",
            actor_kind="client",
        )
    with pytest.raises(SubmissionReportError):
        validate_submission_payload(
            decision="confirmed",
            submitted_on=date.today().isoformat(),
            method=None,
            submitted_what="Пакет",
            source="client_self",
            actor_kind="client",
        )


def test_future_date_rejected() -> None:
    future = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(SubmissionReportError, match="future"):
        validate_submission_payload(
            decision="confirmed",
            submitted_on=future,
            method="sfr",
            submitted_what="Документы",
            source="client_self",
            actor_kind="client",
        )


def test_staff_confirmed_requires_client_words() -> None:
    with pytest.raises(SubmissionReportError, match="client_words"):
        validate_submission_payload(
            decision="confirmed",
            submitted_on=date.today().isoformat(),
            method="mfc",
            submitted_what="Пакет",
            source="client_self",
            actor_kind="staff",
        )


def test_help_requested_skips_date() -> None:
    out = validate_submission_payload(
        decision="help_requested",
        submitted_on=None,
        method=None,
        submitted_what=None,
        source="client_self",
        actor_kind="client",
    )
    assert out["kind"] == "help_requested"
    assert out["submitted_on"] is None


def test_proof_missing_note() -> None:
    assert proof_missing_note(None) == PROOF_MISSING_NOTE
    assert proof_missing_note("doc-1") is None


def test_audit_actions() -> None:
    assert audit_action_for_kind("client_reported") == "submission_confirmed"
    assert audit_action_for_kind("help_requested") == "submission_help_requested"
    assert audit_action_for_kind("receipt_verified") == "submission_receipt_verified"


def test_build_report_row_idempotency() -> None:
    row = build_report_row(
        case_id="c1",
        actor_id="u1",
        actor_kind="client",
        kind="client_reported",
        submitted_on=date.today().isoformat(),
        method="gosuslugi",
        submitted_what="Пакет",
        source="client_self",
        idempotency_key="k1",
    )
    assert row["idempotency_key"] == "k1"
    assert row["case_id"] == "c1"
