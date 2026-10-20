"""Тесты magic bytes и блокировки опасных файлов."""

from __future__ import annotations

from sfrfr.services.file_security import validate_file_bytes, validate_upload_filename


def test_pdf_magic_bytes_ok() -> None:
    data = b"%PDF-1.4 test"
    result = validate_file_bytes(data, filename="doc.pdf", declared_content_type="application/pdf")
    assert result.ok
    assert result.detected_mime == "application/pdf"


def test_jpeg_magic_bytes_ok() -> None:
    data = b"\xff\xd8\xff\xe0" + b"0" * 20
    result = validate_file_bytes(data, filename="scan.jpg")
    assert result.ok


def test_png_magic_bytes_ok() -> None:
    data = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    result = validate_file_bytes(data, filename="scan.png")
    assert result.ok


def test_empty_buffer_rejected() -> None:
    result = validate_file_bytes(b"", filename="doc.pdf")
    assert not result.ok


def test_html_disguised_as_pdf_rejected() -> None:
    result = validate_file_bytes(b"<html>", filename="evil.pdf")
    assert not result.ok


def test_exe_disguised_as_jpg_rejected() -> None:
    result = validate_file_bytes(b"MZ" + b"0" * 20, filename="photo.jpg")
    assert not result.ok


def test_zip_extension_blocked() -> None:
    result = validate_upload_filename("archive.zip")
    assert not result.ok


def test_docx_allowed_for_signed_slot() -> None:
    data = b"PK\x03\x04" + b"0" * 40
    result = validate_file_bytes(data, filename="signed.docx", allow_signed=True)
    assert result.ok


def test_docx_allowed_for_standard_upload() -> None:
    """ТЗ-35 C1: DOCX принимается и без слота подписанного заявления."""
    data = b"PK\x03\x04" + b"0" * 40
    result = validate_file_bytes(data, filename="stazh.docx", allow_signed=False)
    assert result.ok
    assert result.detected_mime is not None
    assert "wordprocessingml" in result.detected_mime


def test_docx_with_macros_rejected() -> None:
    data = b"PK\x03\x04" + b"vbaProject.bin" + b"0" * 40
    result = validate_file_bytes(data, filename="macro.docx", allow_signed=False)
    assert not result.ok
    assert result.internal_reason == "docx_macros"


def test_pdf_with_preamble_accepted() -> None:
    """Часть PDF с телефона/приложений: мусор до %PDF- (допуск ISO)."""
    data = b"\x00\x00" + b"%PDF-1.7 mobile"
    result = validate_file_bytes(data, filename="scan.pdf")
    assert result.ok
    assert result.detected_mime == "application/pdf"


def test_pdf_uppercase_extension_ok() -> None:
    data = b"%PDF-1.4 x"
    result = validate_file_bytes(data, filename="Выписка.PDF")
    assert result.ok


def test_pdf_without_extension_accepted_by_magic() -> None:
    data = b"%PDF-1.4 from max"
    result = validate_file_bytes(data, filename="document")
    assert result.ok
    assert result.detected_mime == "application/pdf"


def test_pdf_with_bin_name_accepted_by_magic() -> None:
    """MAX часто отдаёт вложение без имени → document.bin."""
    data = b"%PDF-1.4 from max"
    result = validate_file_bytes(data, filename="document.bin")
    assert result.ok
    assert result.detected_mime == "application/pdf"


def test_jpeg_misnamed_as_pdf_accepted_as_image() -> None:
    data = b"\xff\xd8\xff\xe0" + b"0" * 20
    result = validate_file_bytes(data, filename="scan.pdf")
    assert result.ok
    assert result.detected_mime == "image/jpeg"


def test_heic_rejected_friendly() -> None:
    data = b"\x00\x00\x00\x18ftypheic" + b"0" * 20
    result = validate_file_bytes(data, filename="photo.heic")
    assert not result.ok
    assert result.internal_reason == "heic_unsupported"
    assert "PDF" not in (result.client_message or "")
    assert "JPEG" not in (result.client_message or "")


def test_client_messages_avoid_latin_format_lists() -> None:
    result = validate_file_bytes(b"MZ" + b"0" * 20, filename="photo.jpg")
    assert not result.ok
    msg = (result.client_message or "").upper()
    for token in ("PDF", "DOCX", "JPG", "JPEG", "PNG"):
        assert token not in msg
