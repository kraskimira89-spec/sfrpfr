"""Нечитаемый посторонний файл не держит «Проверить документы» в «требуется действие»."""

from __future__ import annotations

from sfrfr.services.staff_document_check_result import build_check_result


def _doc(doc_id: str, guessed: str, *, text: bool, ocr: bool = False) -> dict:
    return {
        "id": doc_id,
        "filename": f"{doc_id}.{'png' if ocr else 'pdf'}",
        "checksum_sha256": doc_id,
        "original_available": True,
        "text_extracted": text,
        "needs_ocr": ocr,
        "needs_manual": False,
        "guessed_type": guessed,
    }


def test_extra_unreadable_photo_does_not_block_when_kit_readable() -> None:
    docs = [
        _doc("ils", "ils", text=True),
        _doc("tk", "workbook", text=True),
        _doc("photo", "other", text=False, ocr=True),
    ]
    result = build_check_result(documents=docs, missing_for_task=[], ocr_allowed=False)
    assert result["status"] == "completed"
    assert result["needs_recognition"] == 1
    assert "сверке не мешает" in result["next_action"]
    assert "photo.png" in result["next_action"]


def test_unreadable_ils_still_blocks() -> None:
    docs = [
        _doc("ils", "ils", text=False, ocr=True),
        _doc("tk", "workbook", text=True),
    ]
    result = build_check_result(documents=docs, missing_for_task=[], ocr_allowed=False)
    assert result["status"] == "needs_action"
    assert "распознаван" in result["next_action"].lower()


def test_unreadable_photo_blocks_when_workbook_not_read() -> None:
    docs = [
        _doc("ils", "ils", text=True),
        _doc("photo", "other", text=False, ocr=True),
    ]
    result = build_check_result(documents=docs, missing_for_task=[], ocr_allowed=False)
    assert result["status"] == "needs_action"
