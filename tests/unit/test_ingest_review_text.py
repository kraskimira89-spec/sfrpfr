from sfrfr.services.ingest_review_text import saved_text_payload


def test_saved_text_used_when_no_artifacts() -> None:
    row = {"id": "d1", "content_preview": "ТРУДОВАЯ КНИЖКА " * 200}
    payload = saved_text_payload(row)
    assert payload is not None
    assert payload["fallback"] is True
    assert payload["extracted_text"].startswith("ТРУДОВАЯ КНИЖКА")
    assert payload["truncated"] is True
    assert payload["manifest"]["pages"] == []


def test_no_saved_text_returns_none() -> None:
    assert saved_text_payload({"id": "d2", "content_preview": "  "}) is None
    assert saved_text_payload({"id": "d3"}) is None
