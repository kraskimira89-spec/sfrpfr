"""Ступень 11: разбор ответа СФР."""

from __future__ import annotations

import pytest

from sfrfr.services.response_review import (
    ResponseReviewError,
    build_review_row,
    generate_response_review_draft,
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
    assert out["deadline_quote"] == "в срок до 15 дней"


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
        llm=None,
    )
    assert out["source"] == "template"
    assert out["reason"] == "incomplete_document"
    assert "неполный" in out["text"].lower() or "уточнение" in out["text"].lower()
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


def test_outcomes_allowed() -> None:
    for o in ("need_docs", "offer_escalation", "close", "wait_client"):
        assert validate_outcome(o) == o
