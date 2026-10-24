"""Unit: первичная сверка, резюме, условная рекомендация услуги."""

from __future__ import annotations

from sfrfr.core.audit_ils import compare_ils_vs_labor_book
from sfrfr.services.primary_doc_precheck import (
    PrecheckOutcome,
    build_recommendation,
    run_primary_precheck,
)
from sfrfr.services.primary_doc_precheck_notify import build_precheck_max_message
from sfrfr.services.staff_document_check_result import summarize_for_staff


def test_compare_detects_missing_side() -> None:
    findings = compare_ils_vs_labor_book([], [{"employer": "А", "date_from": "1990-01-01"}])
    assert any(f.get("type") == "missing_in_ils" for f in findings)


def test_date_mismatch_discrepancy_offers_paid() -> None:
    res = run_primary_precheck(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1985-01-01", "date_to": "1990-12-31"}
        ],
        catalog_amount_rub=3000,
        catalog_label="Подробный анализ",
        package_code="diagnostic",
    )
    assert res.outcome == PrecheckOutcome.DISCREPANCIES_FOUND
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is True
    assert "не подтверждает ошибку" in res.client_summary.casefold()


def test_no_discrepancy_does_not_sell() -> None:
    period = {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
    res = run_primary_precheck(
        ils_periods=[period],
        labor_periods=[dict(period)],
        catalog_amount_rub=3000,
    )
    assert res.outcome == PrecheckOutcome.NO_DISCREPANCIES_FOUND
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is False


def test_insufficient_kit_does_not_sell() -> None:
    res = run_primary_precheck(
        ils_periods=[],
        labor_periods=[],
        kit_missing=["ils"],
        catalog_amount_rub=3000,
    )
    assert res.outcome == PrecheckOutcome.INSUFFICIENT_DOCUMENTS
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is False


def test_already_paid_blocks_offer() -> None:
    rec = build_recommendation(
        PrecheckOutcome.DISCREPANCIES_FOUND,
        already_ordered_or_paid=True,
        catalog_amount_rub=3000,
        catalog_label="x",
        package_code="diagnostic",
    )
    assert rec.offer_paid_analysis is False


def test_catalog_missing_no_fake_price() -> None:
    rec = build_recommendation(
        PrecheckOutcome.DISCREPANCIES_FOUND,
        already_ordered_or_paid=False,
        catalog_amount_rub=None,
        catalog_label=None,
        package_code=None,
    )
    assert rec.offer_paid_analysis is False
    assert "каталог" in rec.reason.casefold()


def test_max_buttons_depend_on_outcome() -> None:
    text, atts = build_precheck_max_message(
        {
            "outcome": "no_discrepancies_found",
            "client_summary": "Ок в границах проверки.",
            "recommendation": {"offer_paid_analysis": False},
        }
    )
    assert "Ок" in text
    payloads = str(atts)
    assert "precheck:order" not in payloads

    _, atts2 = build_precheck_max_message(
        {
            "outcome": "discrepancies_found",
            "client_summary": "Есть вопрос по периоду.",
            "recommendation": {"offer_paid_analysis": True},
        }
    )
    assert "precheck:order" in str(atts2)


def test_summarize_overrides_diag_offer_from_primary() -> None:
    card = summarize_for_staff(
        {
            "documents_checked": 2,
            "originals_available": 2,
            "text_extracted": 2,
            "needs_recognition": 0,
            "needs_manual_review": 0,
            "status": "needs_action",
            "diag_offer": {"allowed": True, "amount_rub": 3000, "label": "x"},
            "primary_precheck": {
                "outcome": "no_discrepancies_found",
                "client_summary": "Нет расхождений в объёме.",
                "recommendation": {
                    "offer_paid_analysis": False,
                    "reason": "Нет оснований",
                },
            },
            "client_summary": "Нет расхождений в объёме.",
            "precheck_outcome": "no_discrepancies_found",
        }
    )
    assert card["diag_offer"]["allowed"] is False
    assert card["precheck_outcome"] == "no_discrepancies_found"
