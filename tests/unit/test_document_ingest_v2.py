"""Тесты постраничного ingest v2 и quality gate."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sfrfr.services import document_ingest_v2


def test_failed_page_skips_classification_until_expert_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        document_ingest_v2,
        "_extract_pages",
        lambda data, filename, detected_mime: [
            {
                "page": 1,
                "source": "failed",
                "char_count": 0,
                "engine": "tesseract",
                "error": "tesseract_empty",
                "text": "",
            }
        ],
    )

    def unexpected_pipeline(**kwargs: object) -> dict[str, object]:
        raise AssertionError("classification must wait for HITL review")

    monkeypatch.setattr(document_ingest_v2, "run_ingest_pipeline", unexpected_pipeline)

    result = document_ingest_v2.run_document_ingest_v2(
        data=b"\x89PNG\r\n\x1a\nimage",
        filename="page.png",
        content_type="image/png",
        doc_type="labor",
        active_scenarios=set(),
        duplicate_checksum=False,
        case_id="case-1",
        document_id="doc-1",
    )

    assert result["ingest_status"] == "manual_review"
    assert result["ingest_review_required"] is True
    assert result["manifest"]["needs_ingest_review"] is True
    assert result["manifest"]["pages"][0]["source"] == "failed"


def test_vision_failure_falls_back_to_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        document_ingest_v2,
        "get_settings",
        lambda: SimpleNamespace(ocr_engine="auto", tesseract_lang="rus+eng"),
    )
    monkeypatch.setattr(document_ingest_v2, "_vision_configured", lambda: True)
    monkeypatch.setattr(
        document_ingest_v2,
        "_vision_ocr",
        lambda data: (_ for _ in ()).throw(RuntimeError("vision unavailable")),
    )
    monkeypatch.setattr(document_ingest_v2, "_tesseract_ocr", lambda data, filename: "текст")

    text, source, engine, error = document_ingest_v2._ocr_image(b"image", "page.png")

    assert text == "текст"
    assert source == "ocr_tesseract"
    assert engine == "tesseract"
    assert error is None
