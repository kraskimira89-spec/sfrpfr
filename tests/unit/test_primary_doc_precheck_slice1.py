"""Срез 1 предпроверки: находки + multi-status без MAX/офера."""

from __future__ import annotations

from sfrfr.services.primary_doc_precheck import (
    ComparisonStatus,
    FindingCode,
    PrecheckOutcome,
    compare_period_sources,
    run_primary_precheck,
)
from sfrfr.services.staff_document_check_result import summarize_for_staff


def test_date_mismatch_sets_discrepancy_without_paid_offer() -> None:
    res = run_primary_precheck(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1985-01-01", "date_to": "1990-12-31"}
        ],
        catalog_amount_rub=None,
    )
    assert res.comparison_status == ComparisonStatus.DISCREPANCIES_FOUND
    assert res.outcome == PrecheckOutcome.DISCREPANCIES_FOUND
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is False


def test_empty_periods_not_false_clear() -> None:
    res = run_primary_precheck(ils_periods=[], labor_periods=[], kit_missing=["ils"])
    assert res.outcome != PrecheckOutcome.NO_DISCREPANCIES_FOUND
    assert res.comparison_status != ComparisonStatus.NO_DISCREPANCIES_FOUND


def test_split_ils_rows_no_false_gap() -> None:
    findings = compare_period_sources(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1988-12-31"},
            {"employer": "Завод", "date_from": "1989-01-01", "date_to": "1990-12-31"},
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
    )
    assert any(f.code == FindingCode.MATCHED for f in findings)
    assert not any(f.code == FindingCode.NOT_LOCATED_IN_ILS for f in findings)


def test_identity_conflict_staff() -> None:
    res = run_primary_precheck(
        ils_periods=[{"employer": "A", "date_from": "1987-01-01"}],
        labor_periods=[{"employer": "A", "date_from": "1987-01-01"}],
        identity_conflict=True,
    )
    assert res.data_status.value == "identity_conflict"
    assert res.next_action.value == "staff_review"


def test_summarize_exposes_primary_and_blocks_offer() -> None:
    card = summarize_for_staff(
        {
            "documents_checked": 2,
            "status": "needs_action",
            "diag_offer": {"allowed": True, "amount_rub": 3000},
            "primary_precheck": {
                "outcome": "discrepancies_found",
                "execution_status": "completed",
                "data_status": "partial",
                "comparison_status": "discrepancies_found",
                "client_summary": "Нашли различие по датам.",
                "limitations": ["Часть страниц не проверена"],
                "findings": [
                    {
                        "code": "DATE_DIFFERENCE",
                        "what": "даты",
                        "source_a": "ils",
                        "source_b": "labor",
                    }
                ],
                "areas_checked": ["ils_vs_labor_periods"],
                "rules_version": "primary-doc-precheck-v2",
                "recommendation": {"offer_paid_analysis": True, "reason": "x"},
            },
            "client_summary": "Нашли различие по датам.",
            "document_set_revision": "abc",
            "processor_version": "primary-doc-precheck-v2",
        }
    )
    assert card["diag_offer"]["allowed"] is False
    assert card["comparison_status"] == "discrepancies_found"
    assert card["findings"][0]["code"] == "DATE_DIFFERENCE"
    assert "различие" in str(card["client_summary"]).casefold()
