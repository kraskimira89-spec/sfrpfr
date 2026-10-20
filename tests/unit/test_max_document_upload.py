"""ТЗ-35 C1: приём DOCX из MAX наряду с PDF/фото."""

from __future__ import annotations

from unittest.mock import patch

from sfrfr.services.max_document_upload import upload_max_document


def _docx_bytes() -> bytes:
    return b"PK\x03\x04" + b"0" * 64


def test_upload_max_document_accepts_docx() -> None:
    with patch(
        "sfrfr.services.max_document_upload.create_quarantine_document",
        return_value={"id": "doc-1", "doc_type": None},
    ) as create:
        row = upload_max_document(
            case_id="12345678-1234-1234-1234-123456789012",
            filename="stazh.docx",
            data=_docx_bytes(),
        )
    assert row is not None
    assert row["id"] == "doc-1"
    create.assert_called_once()
    kwargs = create.call_args.kwargs
    assert kwargs["filename"] == "stazh.docx"
    assert kwargs["upload_source"] == "max"
    assert "wordprocessingml" in str(kwargs["content_type"])


def test_upload_max_document_rejects_zip() -> None:
    with patch(
        "sfrfr.services.max_document_upload.create_quarantine_document",
    ) as create:
        row = upload_max_document(
            case_id="12345678-1234-1234-1234-123456789012",
            filename="archive.zip",
            data=_docx_bytes(),
        )
    assert row is None
    create.assert_not_called()


def test_upload_max_document_rejects_legacy_doc() -> None:
    with patch(
        "sfrfr.services.max_document_upload.create_quarantine_document",
    ) as create:
        row = upload_max_document(
            case_id="12345678-1234-1234-1234-123456789012",
            filename="old.doc",
            data=b"\xd0\xcf\x11\xe0" + b"0" * 40,
        )
    assert row is None
    create.assert_not_called()
