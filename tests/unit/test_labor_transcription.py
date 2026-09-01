"""Тесты услуги переноса трудовой."""

from __future__ import annotations

from sfrfr.services.labor_transcription import estimate_transcription


def test_estimate_without_labor_scans() -> None:
    result = estimate_transcription([])
    assert result["status"] == "no_labor_scans"
    assert result["preliminary_total_rub"] == 0


def test_estimate_with_workbook_files() -> None:
    result = estimate_transcription(
        [{"doc_type": "workbook"}, {"doc_type": "workbook", "page_count": 4}]
    )
    assert result["status"] == "estimate_ready"
    assert result["pages_count"] == 3
    assert result["preliminary_total_rub"] == 300
