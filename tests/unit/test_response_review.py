"""Ступень 11: разбор ответа СФР."""

from __future__ import annotations

import pytest

from sfrfr.services.response_review import (
    ResponseReviewError,
    build_review_row,
    generate_response_review_draft,
    is_incoming_response_doc,
    serialize_review,
    validate_outcome,
    validate_register_payload,
)


def test_register_requires_document() -> None:
    with pytest.raises(ResponseReviewError, match="document_id"):
        validate_register_payload({})


def test_register_valid_payload() -> None:
    out = validate_register_payload(
        {
            "document_id": "doc-1",
            "submission_report_id": "sub-1",
            "doc_date": "2026-10-20",
            "doc_number": "42",
            "source": "mail",
            "completeness": "all_pages",
            "respondent": "archive",
            "response_kind": "clarification",
            "deadline_quote": "в срок до 15 дней",
            "deadline_quote_source": "п. 3 ответа",
            "deadline_quote_page": "2",
        }
    )
    assert out["document_id"] == "doc-1"
    assert out["submission_report_id"] == "sub-1"
    assert out["doc_date"] == "2026-10-20"
    assert out["source"] == "mail"
    assert out["completeness"] == "all_pages"
    assert out["respondent"] == "archive"
    assert out["response_kind"] == "clarification"
    assert out["deadline_quote"] == "в срок до 15 дней"


def test_default_respondent_sfr() -> None:
    out = validate_register_payload({"document_id": "d"})
    assert out["respondent"] == "sfr"
    assert out["response_kind"] == "decision"


def test_bad_respondent() -> None:
    with pytest.raises(ResponseReviewError, match="respondent"):
        validate_register_payload({"document_id": "d", "respondent": "tax"})


def test_bad_source_and_outcome() -> None:
    with pytest.raises(ResponseReviewError, match="source"):
        validate_register_payload({"document_id": "x", "source": "telegram"})
    with pytest.raises(ResponseReviewError, match="outcome"):
        validate_outcome("paid")


def test_build_and_serialize_row() -> None:
    validated = validate_register_payload(
        {"document_id": "d1", "source": "staff", "completeness": "unknown"}
    )
    row = build_review_row(
        case_id="c1",
        actor_id="a1",
        validated=validated,
        idempotency_key="idem-1",
    )
    assert row["case_id"] == "c1"
    assert row["status"] == "received"
    ser = serialize_review(row)
    assert ser["document_id"] == "d1"
    assert "idempotency_key" not in ser


def test_incomplete_document_template_not_confident() -> None:
    out = generate_response_review_draft(
        case_ref="CASE",
        response_text="отказ",
        package_summary=None,
        prior_analysis=None,
        completeness="need_more_pages",
        respondent="archive",
        llm=None,
    )
    assert out["source"] == "template"
    assert out["reason"] == "incomplete_document"
    assert "неполный" in out["text"].lower() or "уточнение" in out["text"].lower()
    assert "архив" in out["text"].lower()
    assert "решение принимает сфр" in out["text"].lower()


def test_empty_response_uses_template() -> None:
    out = generate_response_review_draft(
        case_ref="CASE",
        response_text="",
        package_summary=None,
        prior_analysis=None,
        completeness="all_pages",
        llm=None,
    )
    assert out["source"] == "template"
    assert "орган" in out["text"].lower()


def test_outcomes_allowed() -> None:
    for o in ("need_docs", "offer_escalation", "close", "wait_client"):
        assert validate_outcome(o) == o


def test_incoming_doc_filter() -> None:
    assert is_incoming_response_doc({"doc_type": "sfr_decision"})
    assert is_incoming_response_doc({"doc_type": "agency_response"})
    assert is_incoming_response_doc({"storage_path": "x/sfr_refusal.pdf"})
    assert not is_incoming_response_doc({"doc_type": "ils"})


def test_serialize_includes_respondent() -> None:
    ser = serialize_review(
        {
            "id": "r1",
            "case_id": "c1",
            "document_id": "d1",
            "respondent": "court",
            "response_kind": "refusal",
            "status": "received",
        }
    )
    assert ser["respondent"] == "court"
    assert ser["respondent_label"] == "Суд"
    assert ser["response_kind"] == "refusal"
