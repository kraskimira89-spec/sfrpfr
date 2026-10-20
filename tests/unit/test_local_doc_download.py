"""Staff open: краткоживущая ссылка на local quarantine."""

from __future__ import annotations

from pathlib import Path

from sfrfr.services.local_doc_download import (
    issue_local_download,
    reset_for_tests,
    take_local_download,
)


def test_issue_and_take_local_download(tmp_path: Path) -> None:
    reset_for_tests()
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")
    token = issue_local_download(
        path=f,
        filename="a.pdf",
        case_id="c1",
        document_id="d1",
        ttl_sec=60,
    )
    entry = take_local_download(token)
    assert entry is not None
    assert entry.path == f
    assert entry.filename == "a.pdf"
    assert take_local_download("missing") is None
    reset_for_tests()
