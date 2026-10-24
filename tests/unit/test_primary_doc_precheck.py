"""Unit: первичная сверка, резюме, условная рекомендация, MAX-ветки.

Приёмочные сценарии ТЗ §4 (1–12).
"""

from __future__ import annotations

from sfrfr.core.audit_ils import compare_ils_vs_labor_book
from sfrfr.services.primary_doc_precheck import (
    ComparisonStatus,
    FindingCode,
    NextAction,
    PrecheckOutcome,
    build_recommendation,
    compare_period_sources,
    run_primary_precheck,
)
from sfrfr.services.primary_doc_precheck_max import (
    answer_faq,
    resolve_stale_callback,
    sanitize_client_text,
    select_max_branch,
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
    assert res.comparison_status == ComparisonStatus.DISCREPANCIES_FOUND
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is True
    assert "не доказывает ошибку" in res.client_summary.casefold()


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
    assert any("каталог" in x.casefold() for x in rec.limitations)


def test_max_buttons_depend_on_outcome() -> None:
    text, atts = build_precheck_max_message(
        {
            "outcome": "no_discrepancies_found",
            "comparison_status": "no_discrepancies_found",
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
            "comparison_status": "discrepancies_found",
            "next_action": "detailed_analysis",
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


# --- Приёмка ТЗ §4 ---


def test_s1_one_labor_many_ils_rows_no_false_gap() -> None:
    """1. Один период разбит на несколько строк ИЛС — ложного пропуска нет."""
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


def test_s2_employer_rename_not_auto_error() -> None:
    """2. Разные названия одного работодателя — не авто-ошибка."""
    findings = compare_period_sources(
        ils_periods=[
            {
                "employer": "ООО Завод Мечта",
                "date_from": "1987-01-01",
                "date_to": "1990-12-31",
            }
        ],
        labor_periods=[
            {
                "employer": "Завод Мечта",
                "date_from": "1987-01-01",
                "date_to": "1990-12-31",
            }
        ],
    )
    assert not any(
        f.code
        in {
            FindingCode.DATE_DIFFERENCE,
            FindingCode.NOT_LOCATED_IN_ILS,
            FindingCode.SOURCE_CONFLICT,
        }
        for f in findings
    )


def test_s3_uncertain_date_asks_clarification() -> None:
    """3. Дата распознана неуверенно — сначала уточнение."""
    res = run_primary_precheck(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
        labor_periods=[{"employer": "Завод", "date_from": "1987", "date_to": "1990"}],
        catalog_amount_rub=3000,
    )
    assert any(f.code == FindingCode.UNREADABLE_OR_INCOMPLETE for f in res.findings)
    assert res.next_action in {
        NextAction.ANSWER_QUESTION,
        NextAction.STAFF_REVIEW,
        NextAction.UPLOAD_DOCUMENTS,
    }
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is False


def test_s4_no_total_stazh_not_lost() -> None:
    """4. Нет показателя общего стажа — нет автовывода «стаж потерян»."""
    res = run_primary_precheck(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
    )
    blob = " ".join(f.what for f in res.findings) + " " + res.client_summary
    assert "стаж потерян" not in blob.casefold()
    assert "потерянн" not in blob.casefold()


def test_s5_not_located_limited_to_presented_ils() -> None:
    """5. Документальный период без пары — формулировка ограничена выпиской."""
    findings = compare_period_sources(
        ils_periods=[
            {"employer": "Другой", "date_from": "2000-01-01", "date_to": "2001-01-01"}
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
    )
    hit = [f for f in findings if f.code == FindingCode.NOT_LOCATED_IN_ILS]
    assert hit
    assert "представленн" in hit[0].what.casefold() or "илс" in hit[0].what.casefold()


def test_s6_no_discrepancy_no_mandatory_offer() -> None:
    """6. Нет расхождений — нет обязательного платного offer."""
    period = {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
    res = run_primary_precheck(
        ils_periods=[period],
        labor_periods=[dict(period)],
        catalog_amount_rub=3000,
    )
    assert res.comparison_status == ComparisonStatus.NO_DISCREPANCIES_FOUND
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is False
    assert select_max_branch(res.as_dict()) == "clear"
    _, atts = build_precheck_max_message(res.as_dict())
    assert "precheck:order" not in str(atts)


def test_s7_discrepancy_plus_incomplete_both_shown() -> None:
    """7. Расхождение и нечитаемые страницы — и находка, и неполнота."""
    res = run_primary_precheck(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1985-01-01", "date_to": "1990-12-31"}
        ],
        needs_ocr=1,
        catalog_amount_rub=3000,
        package_code="diagnostic",
    )
    assert res.comparison_status == ComparisonStatus.DISCREPANCIES_FOUND
    assert res.data_status.value == "partial"
    assert "ещё не проверен" in res.client_summary.casefold()


def test_s8_paid_blocks_repurchase() -> None:
    """8. Услуга оплачена — повторная покупка не предлагается."""
    res = run_primary_precheck(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1985-01-01", "date_to": "1990-12-31"}
        ],
        already_ordered_or_paid=True,
        catalog_amount_rub=3000,
        package_code="diagnostic",
    )
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is False
    assert res.recommendation.offer_status == "blocked"


def test_s9_client_declined_no_pressure() -> None:
    """9. Клиент отказался — бот не продолжает давление."""
    res = run_primary_precheck(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1985-01-01", "date_to": "1990-12-31"}
        ],
        client_declined_offer=True,
        catalog_amount_rub=3000,
        package_code="diagnostic",
    )
    assert res.recommendation is not None
    assert res.recommendation.offer_status == "declined"
    assert res.recommendation.offer_paid_analysis is False
    faq = answer_faq("не хочу", res.as_dict())
    assert "убираем" in faq.casefold() or "остаётся" in faq.casefold()


def test_s10_stale_callback_shows_current() -> None:
    """10. Старый callback — переход к актуальному результату."""
    current = {
        "comparison_status": "no_discrepancies_found",
        "client_summary": "Актуально: расхождений нет.",
    }
    out = resolve_stale_callback(
        requested_check_id="check-old",
        current_check_id="check-new",
        current_primary=current,
    )
    assert out["stale"] is True
    assert out["action"] == "show_current"
    assert out["check_id"] == "check-new"


def test_s11_banned_llm_phrase_not_sent() -> None:
    """11. LLM пишет «пенсия точно занижена» — текст не отправляется."""
    safe, blocked = sanitize_client_text("Вам пенсия точно занижена, срочно оплатите")
    assert blocked is True
    assert "занижен" not in safe.casefold()
    assert "срочно" not in safe.casefold()


def test_s12_tech_failure_not_commercial() -> None:
    """12. Технический сбой — не коммерческая рекомендация."""
    res = run_primary_precheck(
        ils_periods=[{"employer": "Завод", "date_from": "1987-01-01"}],
        labor_periods=[{"employer": "Завод", "date_from": "1987-01-01"}],
        failed=True,
        catalog_amount_rub=3000,
        package_code="diagnostic",
    )
    assert res.execution_status.value == "failed"
    assert res.recommendation is not None
    assert res.recommendation.offer_paid_analysis is False
    assert select_max_branch(res.as_dict()) == "recover"
    text, atts = build_precheck_max_message(res.as_dict())
    assert "сбоя" in text.casefold() or "не завершена" in text.casefold()
    assert "precheck:order" not in str(atts)


def test_commercial_flags_do_not_change_comparison() -> None:
    """Коммерческая цель не влияет на comparison_status."""
    kwargs = dict(
        ils_periods=[
            {"employer": "Завод", "date_from": "1987-01-01", "date_to": "1990-12-31"}
        ],
        labor_periods=[
            {"employer": "Завод", "date_from": "1985-01-01", "date_to": "1990-12-31"}
        ],
        catalog_amount_rub=3000,
        package_code="diagnostic",
    )
    a = run_primary_precheck(**kwargs)
    b = run_primary_precheck(**kwargs, already_ordered_or_paid=True)
    c = run_primary_precheck(**kwargs, client_declined_offer=True)
    assert a.comparison_status == b.comparison_status == c.comparison_status
    assert [f.code for f in a.findings] == [f.code for f in b.findings]
