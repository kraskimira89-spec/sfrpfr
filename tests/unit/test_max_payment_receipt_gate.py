"""MAX: чек оплаты только при явном ожидании оплаты + сильных признаках."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sfrfr.services.payment_receipt import ingest_max_receipt


def _chain_data(data: list[dict]) -> MagicMock:
    root = MagicMock()
    root.execute.return_value.data = data
    return root


def _clients_table(clients: list[dict]) -> MagicMock:
    table = MagicMock()
    table.select.return_value.eq.return_value.limit.return_value = _chain_data(
        clients
    )
    return table


def _cases_table(cases: list[dict]) -> MagicMock:
    table = MagicMock()
    (
        table.select.return_value.eq.return_value.order.return_value.limit.return_value
    ) = _chain_data(cases)
    return table


def test_labor_pdf_not_ingested_as_receipt_with_draft_order() -> None:
    """PDF трудовой при черновике счёта не уходит в сценарий чека."""
    labor_bytes = b"%PDF-1.4 labor book fake"
    clients = [{"id": "client-1"}]
    cases = [{"id": "case-1"}]
    orders = [
        {
            "id": "ord-1",
            "status": "draft",
            "invoice_status": "draft",
            "amount_rub": 3000,
            "package_code": "DIAG",
        }
    ]

    sb = MagicMock()

    def table(name: str):
        if name == "clients":
            return _clients_table(clients)
        if name == "cases":
            return _cases_table(cases)
        return MagicMock()

    sb.table.side_effect = table

    repo = MagicMock()
    repo.list_orders.return_value = orders

    with (
        patch("sfrfr.db.session.get_supabase_client", return_value=sb),
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.services.payment_receipt.ocr_receipt_bytes",
            return_value=(
                "Трудовая книжка. Оплата труда. Перевод на должность. "
                "Страховой стаж не указан."
            ),
        ) as ocr,
        patch("sfrfr.services.payment_receipt.save_receipt_document") as save_doc,
    ):
        out = ingest_max_receipt(
            max_user_id="42",
            files=[("trudovaya.pdf", labor_bytes)],
        )

    assert out is None
    save_doc.assert_not_called()
    assert ocr.call_count in {0, 1}


def test_receipt_path_only_when_invoice_sent_and_strong_text() -> None:
    """Чек-путь: явный invoice_sent + текст кассового чека с реквизитами."""
    receipt_text = (
        "Кассовый чек. Оплата. ООО ПОД ПРИСМОТРОМ ИНН 8905066468 "
        "р/с 40702810467400005864 сумма 3000,00"
    )
    clients = [{"id": "client-1"}]
    cases = [{"id": "case-1"}]
    orders = [
        {
            "id": "ord-1",
            "status": "pending",
            "invoice_status": "invoice_sent",
            "amount_rub": 3000,
            "package_code": "DIAG",
        }
    ]

    sb = MagicMock()

    def table(name: str):
        if name == "clients":
            return _clients_table(clients)
        if name == "cases":
            return _cases_table(cases)
        return MagicMock()

    sb.table.side_effect = table

    repo = MagicMock()
    repo.list_orders.return_value = orders
    repo.create_payment_record.return_value = None
    repo.apply_provider_payment.return_value = {"newly_paid": True}
    repo.update_order_fields.return_value = None

    with (
        patch("sfrfr.db.session.get_supabase_client", return_value=sb),
        patch("sfrfr.db.case_repository.CaseRepository", return_value=repo),
        patch(
            "sfrfr.services.payment_receipt.ocr_receipt_bytes",
            return_value=receipt_text,
        ),
        patch(
            "sfrfr.services.payment_receipt.save_receipt_document",
            return_value="doc-receipt-1",
        ) as save_doc,
        patch(
            "sfrfr.integrations.payments.notify.notify_payment_succeeded",
            return_value=None,
        ),
    ):
        out = ingest_max_receipt(
            max_user_id="42",
            files=[("check.pdf", b"%PDF-1.4 receipt")],
        )

    assert out is not None
    assert out["status"] == "confirmed"
    save_doc.assert_called_once()
