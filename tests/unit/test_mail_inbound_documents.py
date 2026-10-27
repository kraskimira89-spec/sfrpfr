"""Входящая почта: токен → дело; без токена → needs_binding; без дублей."""

from __future__ import annotations

from pathlib import Path

import pytest

from sfrfr.services.extra_document_intake import make_case_mail_token
from sfrfr.services.mail_inbound_documents import process_inbound_mail_message


class _Repo:
    def __init__(self) -> None:
        self.audits: list[str] = []
        self.tasks: list[str] = []

    def upsert_checklist_item(self, case_id: str, **kwargs: object) -> dict:
        self.tasks.append(str(kwargs.get("title") or ""))
        return {"id": "cl1"}

    def audit(self, case_id: str, actor_id: str | None, action: str) -> None:
        self.audits.append(action)


def test_bound_saves_and_preserves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sfrfr.services import extra_document_intake as edi
    from sfrfr.services import mail_inbound_documents as mid

    monkeypatch.setattr(edi, "default_unbound_root", lambda: tmp_path / "unbound")
    monkeypatch.setattr(edi, "default_mail_processed_root", lambda: tmp_path / "processed")
    monkeypatch.setattr(
        mid,
        "MailInboundProcessedStore",
        lambda: edi.MailInboundProcessedStore(root=tmp_path / "processed"),
    )
    cid = "22222222-2222-2222-2222-222222222222"
    token = make_case_mail_token(cid, secret="sec")
    repo = _Repo()
    saved_docs: list[dict] = []

    def _store(**kwargs: object) -> dict:
        doc = {"id": f"d{len(saved_docs)+1}", "doc_type": kwargs.get("doc_type")}
        saved_docs.append(doc)
        return doc

    out = process_inbound_mail_message(
        message_id="<m1@x>",
        subject=f"docs [SFRFR-DOC {token}]",
        sender="client@example.com",
        attachments=[("spravka.pdf", b"%PDF-1.4", "application/pdf")],
        known_case_ids=[cid],
        store_document_fn=_store,
        repo=repo,
        secret="sec",
    )
    assert out["bound"] is True
    assert out["preserves_funnel"] is True
    assert len(saved_docs) == 1
    assert repo.tasks


def test_unbound_without_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sfrfr.services import extra_document_intake as edi
    from sfrfr.services import mail_inbound_documents as mid

    unbound = tmp_path / "unbound"
    processed = tmp_path / "processed"
    monkeypatch.setattr(edi, "default_unbound_root", lambda: unbound)
    monkeypatch.setattr(edi, "default_mail_processed_root", lambda: processed)
    monkeypatch.setattr(
        mid, "UnboundMailQueue", lambda: edi.UnboundMailQueue(root=unbound)
    )
    monkeypatch.setattr(
        mid,
        "MailInboundProcessedStore",
        lambda: edi.MailInboundProcessedStore(root=processed),
    )

    out = process_inbound_mail_message(
        message_id="<m2@x>",
        subject="справка Иванова",
        sender="ivanov@example.com",
        attachments=[("a.pdf", b"x", "application/pdf")],
        known_case_ids=["22222222-2222-2222-2222-222222222222"],
        store_document_fn=lambda **_: {"id": "no"},
        repo=_Repo(),
        secret="sec",
    )
    assert out["bound"] is False
    assert out["status"] == "needs_binding"
    item = out["queue_item"]
    assert item.get("blobs_saved") == 1
    q = edi.UnboundMailQueue(root=tmp_path / "unbound")
    blobs = q.load_attachment_blobs(item["id"])
    assert len(blobs) == 1
    assert blobs[0][0] == "a.pdf"
    assert blobs[0][1] == b"x"


def test_bind_unbound_materializes_attachments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sfrfr.services import extra_document_intake as edi
    from sfrfr.services import mail_inbound_documents as mid
    from sfrfr.services.extra_document_intake import bind_unbound_mail_to_case

    root = tmp_path / "unbound"
    processed = tmp_path / "processed"
    monkeypatch.setattr(edi, "default_unbound_root", lambda: root)
    monkeypatch.setattr(edi, "default_mail_processed_root", lambda: processed)
    monkeypatch.setattr(mid, "UnboundMailQueue", lambda: edi.UnboundMailQueue(root=root))
    monkeypatch.setattr(
        mid,
        "MailInboundProcessedStore",
        lambda: edi.MailInboundProcessedStore(root=processed),
    )

    out = process_inbound_mail_message(
        message_id="<m3@x>",
        subject="без токена",
        sender="a@b.ru",
        attachments=[
            ("one.pdf", b"AAA", "application/pdf"),
            ("two.pdf", b"BBB", "application/pdf"),
        ],
        known_case_ids=[],
        store_document_fn=lambda **_: {"id": "skip"},
        repo=_Repo(),
        secret="sec",
    )
    item_id = out["queue_item"]["id"]
    saved: list[str] = []

    def _store(**kwargs: object) -> dict:
        saved.append(str(kwargs.get("filename")))
        return {"id": f"doc-{len(saved)}", "doc_type": kwargs.get("doc_type")}

    cid = "33333333-3333-3333-3333-333333333333"
    bound = bind_unbound_mail_to_case(
        item_id=item_id,
        case_id=cid,
        actor_id="staff-1",
        store_document_fn=_store,
        repo=_Repo(),
        queue=edi.UnboundMailQueue(root=root),
    )
    assert bound["ok"] is True
    assert bound["preserves_funnel"] is True
    assert saved == ["one.pdf", "two.pdf"]
    assert edi.UnboundMailQueue(root=root).list_pending() == []


def test_inbound_dedup_by_message_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sfrfr.services import extra_document_intake as edi
    from sfrfr.services import mail_inbound_documents as mid

    root = tmp_path / "unbound"
    processed = tmp_path / "processed"
    monkeypatch.setattr(edi, "default_unbound_root", lambda: root)
    monkeypatch.setattr(edi, "default_mail_processed_root", lambda: processed)
    monkeypatch.setattr(mid, "UnboundMailQueue", lambda: edi.UnboundMailQueue(root=root))
    monkeypatch.setattr(
        mid,
        "MailInboundProcessedStore",
        lambda: edi.MailInboundProcessedStore(root=processed),
    )

    kwargs = dict(
        message_id="<dup@x>",
        subject="без токена",
        sender="a@b.ru",
        attachments=[("a.pdf", b"1", "application/pdf")],
        known_case_ids=[],
        store_document_fn=lambda **_: {"id": "x"},
        repo=_Repo(),
        secret="sec",
    )
    first = process_inbound_mail_message(**kwargs)
    second = process_inbound_mail_message(**kwargs)
    assert first["status"] == "needs_binding"
    assert second.get("deduped") is True
    assert edi.UnboundMailQueue(root=root).list_pending().__len__() == 1
