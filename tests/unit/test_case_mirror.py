"""Тесты зеркала Яндекс.Диск."""

from __future__ import annotations

from sfrfr.integrations.yandex_workspace.case_mirror import mirror_case_document_safe


def test_bank_statement_not_mirrored() -> None:
    result = mirror_case_document_safe(
        "case-1", "bank.pdf", b"%PDF", doc_type="bank_statement"
    )
    assert result.get("skipped") is True
    assert result.get("reason") == "bank_statement_no_mirror"
