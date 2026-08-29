"""Канбан продаж и LOSS без amo."""

from __future__ import annotations

from sfrfr.services.sales_board import LOSS_REASON_VALUES, sales_board_column


def test_sales_board_new_lead() -> None:
    assert (
        sales_board_column(pipeline_status="intake", b2c_status="lead") == "new"
    )


def test_sales_board_payment() -> None:
    assert (
        sales_board_column(
            pipeline_status="documents_received",
            b2c_status="consent_accepted",
            waiting_on="payment",
        )
        == "payment"
    )


def test_sales_board_lost_vs_closed() -> None:
    assert (
        sales_board_column(
            pipeline_status="completed",
            b2c_status="closed",
            loss_reason="цена",
        )
        == "lost"
    )
    assert (
        sales_board_column(pipeline_status="completed", b2c_status="closed")
        == "closed"
    )


def test_loss_reasons_non_empty() -> None:
    assert "цена" in LOSS_REASON_VALUES
    assert "другое" in LOSS_REASON_VALUES
