from sfrfr.services.staff_artifact_replace import text_from_upload


def test_text_from_txt() -> None:
    assert text_from_upload(filename="a.txt", data="Привет\n".encode()) == "Привет"


def test_text_rejects_pdf() -> None:
    try:
        text_from_upload(filename="x.pdf", data=b"%PDF")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "docx" in str(exc).lower() or "txt" in str(exc).lower()
