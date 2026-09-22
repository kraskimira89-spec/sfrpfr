"""MAX ingest: успех только при записи в Supabase, без silent local."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from sfrfr.integrations.max import handler as max_handler


def test_ingest_max_file_false_when_supabase_fails(monkeypatch) -> None:
    import sfrfr.services.max_document_upload as mdu

    monkeypatch.setattr(mdu, "upload_max_document", lambda **_kwargs: None)
    ok = max_handler._ingest_max_file(
        case_id="11111111-1111-1111-1111-111111111111",
        filename="ils.pdf",
        data=b"%PDF-1.4",
        store=MagicMock(),
        record=SimpleNamespace(case_id="local-1"),
    )
    assert ok is False


def test_ingest_max_file_true_when_supabase_ok(monkeypatch) -> None:
    import sfrfr.integrations.max.case_chat_log as clog
    import sfrfr.services.max_document_upload as mdu

    monkeypatch.setattr(mdu, "upload_max_document", lambda **_kwargs: {"id": "doc-1"})
    logged: list[dict] = []
    monkeypatch.setattr(clog, "append_case_chat_message", lambda **kwargs: logged.append(kwargs))
    monkeypatch.setattr(clog, "format_document_event", lambda **_k: "doc event")
    ok = max_handler._ingest_max_file(
        case_id="11111111-1111-1111-1111-111111111111",
        filename="ils.pdf",
        data=b"%PDF-1.4",
        store=MagicMock(),
        record=SimpleNamespace(case_id="local-1"),
    )
    assert ok is True
    assert logged
