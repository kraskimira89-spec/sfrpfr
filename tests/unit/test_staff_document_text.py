"""Staff: полный текст и краткое описание раздельно (выпуск 1)."""

from __future__ import annotations

from sfrfr.api.routes.admin_portal import _staff_documents


def _raw_doc(**extra: object) -> dict:
    base = {
        "id": "d1",
        "storage_path": "case/d1/scan.pdf",
        "doc_type": "ils_extract",
        "created_at": "2026-10-21T10:00:00+00:00",
        "antivirus_status": "clean",
        "ingest_status": "ocr_done",
        "mime_verified": "application/pdf",
    }
    base.update(extra)
    return base


def test_staff_ocr_gets_full_preview_and_separate_summary() -> None:
    long_text = ("Абзац про стаж. " * 40).strip()  # > 280 символов
    assert len(long_text) > 280
    docs = _staff_documents([_raw_doc(content_preview=long_text)], can_view_ocr=True)
    assert len(docs) == 1
    doc = docs[0]
    # Полный текст из БД (без обрезки клиентским лимитом 280).
    assert doc.get("content_preview") == long_text or (
        isinstance(doc.get("content_preview"), str)
        and len(str(doc["content_preview"])) > 280
        and str(doc["content_preview"]).startswith("Абзац про стаж")
    )
    summary = str(doc.get("content_summary") or "")
    assert summary
    assert len(summary) <= 281  # 280 + возможное «…»
    assert summary != doc.get("content_preview")


def test_staff_without_full_text_does_not_fake_preview_from_empty() -> None:
    docs = _staff_documents([_raw_doc(content_preview="")], can_view_ocr=True)
    doc = docs[0]
    assert doc.get("content_preview") in (None, "")
    assert doc.get("content_summary") in (None, "")


def test_operator_still_hides_preview() -> None:
    docs = _staff_documents(
        [_raw_doc(content_preview="Секретный OCR текст стажа")],
        can_view_ocr=False,
    )
    doc = docs[0]
    assert "content_preview" not in doc or doc.get("content_preview") is None
    assert "content_summary" not in doc or doc.get("content_summary") is None
