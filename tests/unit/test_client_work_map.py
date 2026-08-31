"""Карта клиентского кабинета: понятные статусы без pipeline/OCR."""

from __future__ import annotations

from sfrfr.services.client_work_map import build_client_work_map, document_slots


def test_waiting_docs_when_empty() -> None:
    work = build_client_work_map(
        pipeline_status="intake",
        b2c_status="consent_accepted",
        consent_accepted=True,
        documents=[],
        checklist_items=[
            {"title": "Выписка ИЛС", "status": "open", "owner": "client", "item_type": "document"},
            {
                "title": "Трудовая книжка / сведения о стаже",
                "status": "open",
                "owner": "client",
                "item_type": "document",
            },
        ],
        orders=[],
    )
    assert work["status_key"] == "waiting_docs"
    assert "ИЛС" in work["now_need"]
    assert work["cta_key"] == "upload"
    assert work["required_uploaded"] == 0
    assert work["required_total"] == 2
    assert work["order"]["state"] == "not_agreed"


def test_document_slot_awaiting_after_upload() -> None:
    slots, uploaded, total = document_slots(
        [
            {
                "id": "d1",
                "doc_type": "ils",
                "created_at": "2026-08-31T15:40:00+00:00",
            }
        ],
        [
            {"title": "Выписка ИЛС", "status": "open"},
            {"title": "Трудовая книжка / сведения о стаже", "status": "open"},
        ],
    )
    ils = next(s for s in slots if s["key"] == "ils")
    labor = next(s for s in slots if s["key"] == "labor")
    assert ils["status"] == "awaiting"
    assert "ожидает" in ils["status_label"]
    assert ils["can_delete"] is True
    assert ils["added_at"] == "31 августа, 18:40"
    assert labor["status"] == "missing"
    assert uploaded == 1
    assert total == 2


def test_accepted_slot_no_delete() -> None:
    slots, _uploaded, _total = document_slots(
        [{"id": "d1", "doc_type": "ils", "created_at": "2026-08-31T15:40:00+00:00"}],
        [{"title": "Выписка ИЛС", "status": "done"}],
    )
    ils = next(s for s in slots if s["key"] == "ils")
    assert ils["status"] == "accepted"
    assert ils["can_delete"] is False


def test_docs_review_after_both_uploaded() -> None:
    work = build_client_work_map(
        pipeline_status="intake",
        b2c_status="consent_accepted",
        consent_accepted=True,
        documents=[
            {"id": "a", "doc_type": "ils"},
            {"id": "b", "doc_type": "workbook"},
        ],
        checklist_items=[],
        orders=[{"id": "o1", "package_code": "DIAG", "amount_rub": 3000, "status": "paid"}],
    )
    assert work["status_key"] == "docs_review"
    assert work["cta_key"] == "wait"
    assert work["order"]["can_pay"] is False
    assert work["order"]["status_label"] == "Оплата получена"
    assert work["result"]["ready"] is False
    stages = {row["n"]: row["state"] for row in work["stages"]}
    assert stages[1] == "done"
    assert stages[2] == "done"
    assert stages[3] == "current"
    assert stages[4] == "todo"


def test_no_raw_pipeline_codes_in_client_copy() -> None:
    work = build_client_work_map(
        pipeline_status="ocr_done",
        b2c_status="documents_received",
        consent_accepted=True,
        documents=[
            {"id": "a", "doc_type": "ils"},
            {"id": "b", "doc_type": "workbook"},
        ],
        checklist_items=[],
        orders=[{"id": "o1", "package_code": "DIAG", "amount_rub": 3000, "status": "pending"}],
    )
    blob = str(work).lower()
    assert "ocr" not in blob
    assert "intake" not in blob
    assert "pending" not in blob
    assert work["order"]["status_label"] == "Ожидает оплаты"
    assert work["cta_key"] == "pay"


def test_untyped_upload_fills_ils_slot() -> None:
    slots, uploaded, total = document_slots(
        [{"id": "scan", "doc_type": None, "created_at": "2026-08-31T15:40:00+00:00"}],
        [
            {"title": "Выписка ИЛС", "status": "open"},
            {"title": "Трудовая книжка / сведения о стаже", "status": "open"},
        ],
    )
    ils = next(s for s in slots if s["key"] == "ils")
    labor = next(s for s in slots if s["key"] == "labor")
    extra = next(s for s in slots if s["key"] == "extra")
    assert ils["status"] == "awaiting"
    assert ils["document_id"] == "scan"
    assert labor["status"] == "missing"
    assert extra["status"] == "missing"
    assert uploaded == 1
    assert total == 2


def test_two_untyped_uploads_fill_required_slots() -> None:
    slots, uploaded, _total = document_slots(
        [
            {"id": "first", "created_at": "2026-08-31T10:00:00+00:00"},
            {"id": "second", "created_at": "2026-08-31T11:00:00+00:00"},
        ],
        [],
    )
    ils = next(s for s in slots if s["key"] == "ils")
    labor = next(s for s in slots if s["key"] == "labor")
    assert ils["document_id"] == "first"
    assert labor["document_id"] == "second"
    assert uploaded == 2


def test_full_checklist_has_core_and_pension_rows() -> None:
    slots, uploaded, total = document_slots([], [])
    keys = [s["key"] for s in slots]
    assert keys[:2] == ["ils", "labor"]
    assert "bank" in keys
    assert "sfr_pay" in keys
    assert "sfr_size" in keys
    assert "military" in keys
    assert "children" in keys
    assert "north" in keys
    assert "sfr" in keys
    assert all(s["status"] == "missing" for s in slots)
    assert uploaded == 0
    assert total == 2


def test_result_ready_only_with_diagnosis_pdf() -> None:
    work = build_client_work_map(
        pipeline_status="audited",
        b2c_status="diagnostic_paid",
        consent_accepted=True,
        documents=[
            {"id": "a", "doc_type": "ils"},
            {"id": "b", "doc_type": "workbook"},
            {
                "id": "pdf",
                "doc_type": "diagnosis_report",
                "created_at": "2026-09-05T10:00:00+00:00",
            },
        ],
        checklist_items=[],
    )
    assert work["status_key"] in {"result_ready", "done"}
    assert work["result"]["ready"] is True
    assert work["result"]["document_id"] == "pdf"
