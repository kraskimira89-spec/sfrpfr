from sfrfr.services.staff_ops_facts import format_ops_facts_for_llm, ops_facts_from_check_and_orders


def test_ops_facts_prefers_discrepancy_over_payment_ask() -> None:
    facts = ops_facts_from_check_and_orders(
        check={
            "status": "completed",
            "result": {
                "unique_documents": 3,
                "honest_brief": {
                    "items": [
                        {
                            "text": (
                                "Северный стаж учтён не за весь период "
                                "работы 01.02.1989–04.10.1999"
                            ),
                            "evidence": "docs",
                            "basis": "В ИЛС отметка только за 01.01.1998–04.10.1999.",
                        },
                        {"text": "по северному стажу", "evidence": "needs_check"},
                    ]
                },
                "stazh_compare": {
                    "ran": True,
                    "discrepancies": 1,
                    "summary": "найдено расхождений: 1.",
                },
                "diag_offer": {"allowed": True},
            },
        },
        orders=[
            {"package_code": "DIAG", "amount_rub": 1, "status": "paid"},
            {"package_code": "ACCOMP", "amount_rub": 5000, "status": "pending"},
        ],
    )
    assert facts["check_status"] == "completed"
    assert facts["diag_paid"] is True
    assert facts["support_or_accomp_pending"] is True
    assert facts["staff_next"] == "prepare_analysis"
    assert len(facts["discrepancies"]) == 1
    assert "01.02.1989" in facts["discrepancies"][0]
    text = format_ops_facts_for_llm(facts)
    assert "DIAG оплачен" in text
    assert "не предлагай снова оплату diag" in text.lower()
    assert "prepare_analysis" in text


def test_ops_facts_asks_payment_only_when_unpaid_and_docs_ok() -> None:
    facts = ops_facts_from_check_and_orders(
        check={
            "status": "completed",
            "result": {
                "honest_brief": {
                    "items": [{"text": "Период не найден в ИЛС", "evidence": "docs"}],
                    "offer_diag_allowed": True,
                },
                "diag_offer": {"allowed": True},
            },
        },
        orders=[{"package_code": "DIAG", "amount_rub": 3000, "status": "pending"}],
    )
    assert facts["diag_paid"] is False
    assert facts["staff_next"] == "wait_diag_payment"
    unpaid = ops_facts_from_check_and_orders(
        check={
            "status": "completed",
            "result": {
                "honest_brief": {
                    "items": [{"text": "Период не найден в ИЛС", "evidence": "docs"}],
                },
                "diag_offer": {"allowed": True},
            },
        },
        orders=[],
    )
    assert unpaid["staff_next"] == "offer_or_wait_diag"


def test_ops_facts_empty_without_check() -> None:
    facts = ops_facts_from_check_and_orders(check=None, orders=[])
    assert facts["check_status"] == "none"
    assert facts["discrepancies"] == []
    assert format_ops_facts_for_llm(facts)
