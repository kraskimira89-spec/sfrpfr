from sfrfr.services.appeal_docx import build_appeal_docx_bytes, draft_payload_from_case


def test_build_appeal_docx_bytes_non_empty() -> None:
    raw = build_appeal_docx_bytes(title="Обращение", body="Прошу учесть стаж.", case_ref="ПС-1")
    assert raw[:2] == b"PK"
    assert len(raw) > 1000


def test_draft_payload_from_case() -> None:
    title, body = draft_payload_from_case(
        {"draft": {"title": "T", "body": "B"}, "case_number": "X"}
    )
    assert title == "T"
    assert body == "B"
