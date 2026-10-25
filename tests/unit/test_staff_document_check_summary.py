from sfrfr.services.staff_document_check_result import summarize_for_staff


def _doc(name: str, checksum: str, *, ocr: bool = False, manual: bool = False) -> dict:
    return {
        "filename": name,
        "checksum_sha256": checksum,
        "needs_ocr": ocr,
        "needs_manual": manual,
        "text_extracted": not ocr,
    }


def test_summary_counts_unique_files_and_names_unreadable() -> None:
    result = {
        "documents_checked": 5,
        "documents": [
            _doc("tk.docx", "a"),
            _doc("tk.docx", "a"),
            _doc("ils.pdf", "b"),
            _doc("scan.png", "c", ocr=True),
            _doc("scan.png", "c", ocr=True),
        ],
    }
    out = summarize_for_staff(result)
    assert out["unique_documents"] == 3
    assert out["unreadable_files"] == ["scan.png"]
    assert out["manual_files"] == []


def test_unreadable_core_counts_only_ils_and_workbook() -> None:
    result = {
        "documents_checked": 2,
        "documents": [
            {**_doc("scan.png", "c", ocr=True), "guessed_type": "other"},
            {**_doc("ils_photo.jpg", "d", ocr=True), "guessed_type": "ils"},
        ],
    }
    assert summarize_for_staff(result)["unreadable_core"] == 1


def test_summary_without_documents_list_falls_back() -> None:
    out = summarize_for_staff({"documents_checked": 2})
    assert out["unique_documents"] == 2
    assert out["unreadable_files"] == []
