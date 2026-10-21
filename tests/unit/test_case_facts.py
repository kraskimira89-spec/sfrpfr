"""Schema сведений/расхождений: цитаты, no invent, HITL."""

from __future__ import annotations

from sfrfr.services.case_facts import (
    apply_specialist_review,
    normalize_findings_to_discrepancies,
    pending_specialist_questions,
)


def test_normalize_without_inventing_missing_citations() -> None:
    bundle = normalize_findings_to_discrepancies(
        [{"type": "missing_in_ils", "detail": "Период 2010–2012 есть в трудовой, нет в ИЛС"}],
        documents=[{"id": "11111111-1111-1111-1111-111111111111"}],
    )
    assert bundle.invented is False
    assert len(bundle.discrepancies) == 1
    d = bundle.discrepancies[0]
    assert d.left is None  # нет document_id/quote в raw — не выдумываем
    assert "трудовой" in d.summary


def test_normalize_keeps_explicit_citation() -> None:
    doc = "22222222-2222-2222-2222-222222222222"
    bundle = normalize_findings_to_discrepancies(
        [
            {
                "type": "date_mismatch",
                "detail": "Дата приёма отличается",
                "document_id": doc,
                "quote": "принят 12.03.2010",
                "page": 2,
                "other_document_id": doc,
                "other_quote": "с 01.03.2010",
                "other_page": 1,
            }
        ],
        documents=[{"id": doc}],
    )
    d = bundle.discrepancies[0]
    assert d.left is not None
    assert d.left.document_id == doc
    assert d.left.quote == "принят 12.03.2010"
    assert d.left.page == 2
    assert d.right is not None
    assert d.right.page == 1


def test_drops_foreign_document_id() -> None:
    bundle = normalize_findings_to_discrepancies(
        [
            {
                "type": "x",
                "detail": "something",
                "document_id": "99999999-9999-9999-9999-999999999999",
                "quote": "q",
            }
        ],
        documents=[{"id": "11111111-1111-1111-1111-111111111111"}],
    )
    assert bundle.discrepancies[0].left is not None
    assert bundle.discrepancies[0].left.document_id is None
    assert bundle.discrepancies[0].left.quote == "q"


def test_specialist_review_preserves_original() -> None:
    bundle = normalize_findings_to_discrepancies(
        [{"type": "x", "detail": "Исходная формулировка", "id": "abc"}]
    )
    updated = apply_specialist_review(
        bundle,
        discrepancy_id="abc",
        status="corrected",
        correction="Уточнённая формулировка",
        actor_id="staff-1",
        reviewed_at="2026-10-21T12:00:00Z",
    )
    d = updated.discrepancies[0]
    assert d.original_summary == "Исходная формулировка"
    assert d.summary == "Уточнённая формулировка"
    assert d.correction == "Уточнённая формулировка"
    assert d.reviewed_by == "staff-1"
    assert d.status == "corrected"
    assert d.needs_specialist is False


def test_pending_questions_are_specific() -> None:
    bundle = normalize_findings_to_discrepancies(
        [
            {
                "type": "date_mismatch",
                "detail": "Дата увольнения в ИЛС и трудовой разная",
                "document_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "quote": "уволен 01.02.2015",
                "page": 3,
            }
        ],
        documents=[{"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}],
    )
    qs = pending_specialist_questions(bundle)
    assert len(qs) == 1
    assert "Сверьте:" in qs[0]
    assert "стр. 3" in qs[0]
