"""Тесты ingest-pipeline: классификация и предложение размещения."""

from __future__ import annotations

from sfrfr.services.document_ingest import run_ingest_pipeline
from sfrfr.services.document_requirements import SCENARIO_PAYOUT_RECONCILIATION


def test_ingest_suggests_ils_from_preview() -> None:
    preview = "Выписка из индивидуального лицевого счёта СФР от 01.01.2024"
    data = b"%PDF-1.4\n" + preview.encode("utf-8")
    result = run_ingest_pipeline(
        data=data,
        filename="ils.pdf",
        content_type="application/pdf",
        doc_type="ils",
        preview_text=preview,
        active_scenarios=set(),
        duplicate_checksum=False,
    )
    assert result["ingest_status"] in {"under_review", "manual_review"}
    assert result["placement_suggestion"]["requirement_code"] == "ils_statement"


def test_bank_blocked_without_scenario() -> None:
    preview = "Выписка по счёту пенсионных выплат"
    data = b"%PDF-1.4\n" + preview.encode("utf-8")
    result = run_ingest_pipeline(
        data=data,
        filename="bank.pdf",
        content_type="application/pdf",
        doc_type="bank_statement",
        preview_text=preview,
        active_scenarios=set(),
        duplicate_checksum=False,
    )
    assert result["ingest_status"] == "blocked_security"


def test_bank_allowed_with_payout_scenario() -> None:
    preview = "Выписка по счёту пенсионных выплат за 12 месяцев"
    data = b"%PDF-1.4\n" + preview.encode("utf-8")
    result = run_ingest_pipeline(
        data=data,
        filename="bank.pdf",
        content_type="application/pdf",
        doc_type="bank_statement",
        preview_text=preview,
        active_scenarios={SCENARIO_PAYOUT_RECONCILIATION},
        duplicate_checksum=False,
    )
    assert result["ingest_status"] != "blocked_security"
