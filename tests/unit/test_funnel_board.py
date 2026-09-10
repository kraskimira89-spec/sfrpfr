"""Kanban воронки 3/5/8 (ТЗ-33)."""

from __future__ import annotations

from sfrfr.services.funnel_board import (
    classify_accomp_tariff,
    compute_funnel_column,
    diagnosis_delivered_from_case,
)


def test_classify_accomp_by_amount() -> None:
    assert classify_accomp_tariff({"package_code": "ACCOMP", "amount_rub": 5000}) == "DOCS"
    assert classify_accomp_tariff({"package_code": "ACCOMP", "amount_rub": 8000}) == "SUPPORT"


def test_diag_paid_column() -> None:
    case = {"pipeline_status": "documents_received", "b2c_status": "diagnostic_paid"}
    orders = [{"package_code": "DIAG", "status": "paid"}]
    assert compute_funnel_column(case, orders) == "diag_work"


def test_diag_done_after_delivery() -> None:
    case = {
        "pipeline_status": "documents_received",
        "b2c_status": "diagnostic_paid",
        "diagnostic_results": [{"status": "link_issued"}],
    }
    orders = [{"package_code": "DIAG", "status": "paid"}]
    assert compute_funnel_column(case, orders) == "diag_done"
    assert diagnosis_delivered_from_case(case) is True


def test_pay_docs_and_docs_work() -> None:
    case = {"pipeline_status": "documents_received", "b2c_status": "diagnostic_paid"}
    open_docs = [
        {"package_code": "DIAG", "status": "paid"},
        {
            "package_code": "ACCOMP",
            "status": "draft",
            "amount_rub": 5000,
            "service_label": "Шаг 2. Подготовка документов",
            "invoice_status": "draft",
        },
    ]
    assert compute_funnel_column(case, open_docs) == "pay_docs"
    paid_docs = [
        {"package_code": "DIAG", "status": "paid"},
        {"package_code": "ACCOMP", "status": "paid", "amount_rub": 5000},
    ]
    assert compute_funnel_column(case, paid_docs) == "docs_work"


def test_pay_support_and_support() -> None:
    case = {"pipeline_status": "draft_ready", "b2c_status": "service_paid"}
    open_sup = [
        {"package_code": "DIAG", "status": "paid"},
        {"package_code": "ACCOMP", "status": "paid", "amount_rub": 5000},
        {
            "package_code": "ACCOMP",
            "status": "pending",
            "amount_rub": 8000,
            "service_label": "Шаг 3. Сопровождение до подачи",
        },
    ]
    assert compute_funnel_column(case, open_sup) == "pay_support"
    paid = [
        {"package_code": "DIAG", "status": "paid"},
        {"package_code": "ACCOMP", "status": "paid", "amount_rub": 5000},
        {"package_code": "ACCOMP", "status": "paid", "amount_rub": 8000},
    ]
    assert compute_funnel_column(case, paid) == "support"


def test_lost_and_new() -> None:
    assert (
        compute_funnel_column(
            {"pipeline_status": "completed", "b2c_status": "closed", "loss_reason": "цена"},
            [],
        )
        == "lost"
    )
    assert (
        compute_funnel_column({"pipeline_status": "intake", "b2c_status": "lead"}, [])
        == "new"
    )


def test_manual_override() -> None:
    case = {
        "pipeline_status": "intake",
        "b2c_status": "lead",
        "funnel_column_manual": "diag_work",
    }
    assert compute_funnel_column(case, []) == "diag_work"
