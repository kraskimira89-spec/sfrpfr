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


def test_align_filename_bin_pdf() -> None:
    from sfrfr.services.file_security import align_filename_to_content

    assert align_filename_to_content("document.bin", b"%PDF-1.4 x") == "document.pdf"
    assert align_filename_to_content("scan.bin", b"\xff\xd8\xff\xe0" + b"0" * 20) == "scan.jpg"
    assert (
        align_filename_to_content("photo.bin", b"\x89PNG\r\n\x1a\n" + b"0" * 20) == "photo.png"
    )


def test_max_upload_accepts_bin_when_pdf(monkeypatch) -> None:
    from sfrfr.services import max_document_upload as mod

    captured: dict = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return {"id": "doc-1", "ok": True}

    monkeypatch.setattr(mod, "create_quarantine_document", fake_create)
    row = mod.upload_max_document(
        case_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        filename="document.bin",
        data=b"%PDF-1.4 content",
    )
    assert row is not None
    assert captured["filename"] == "document.pdf"
    assert captured["content_type"] == "application/pdf"