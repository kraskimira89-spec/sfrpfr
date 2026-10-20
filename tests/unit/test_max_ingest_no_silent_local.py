"""MAX ingest: без case_id — отказ; при облаке pending — успех с id."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from sfrfr.integrations.max import handler as max_handler


def test_ingest_max_file_false_when_upload_returns_none(monkeypatch) -> None:
    import sfrfr.services.max_document_upload as mdu

    monkeypatch.setattr(mdu, "upload_max_document", lambda **_k: None)
    store = MagicMock()
    ok = max_handler._ingest_max_file(
        case_id="11111111-1111-1111-1111-111111111111",
        filename="ils.pdf",
        data=b"%PDF-1.4",
        store=store,
        record=SimpleNamespace(case_id="local-1"),
    )
    assert ok is None
    store.add_document.assert_not_called()


def test_ingest_max_file_false_when_case_id_empty(monkeypatch) -> None:
    import sfrfr.services.max_document_upload as mdu

    monkeypatch.setattr(
        mdu,
        "upload_max_document",
        lambda **_k: (_ for _ in ()).throw(AssertionError("must not upload")),
    )
    ok = max_handler._ingest_max_file(
        case_id="",
        filename="ils.pdf",
        data=b"%PDF-1.4",
        store=MagicMock(),
        record=SimpleNamespace(case_id="local-1"),
    )
    assert ok is None


def test_ingest_max_file_true_when_supabase_ok(monkeypatch) -> None:
    import sfrfr.integrations.max.case_chat_log as clog
    import sfrfr.services.max_document_upload as mdu

    monkeypatch.setattr(
        mdu,
        "upload_max_document",
        lambda **_kwargs: {"id": "doc-1", "cloud_status": "ok"},
    )
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
    assert ok == "doc-1"
    assert logged
