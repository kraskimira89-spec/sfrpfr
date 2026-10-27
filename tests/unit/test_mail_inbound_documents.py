"""Входящая почта: токен → дело; без токена → needs_binding; без дублей."""

from __future__ import annotations

from pathlib import Path

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


def test_bound_saves_and_preserves(tmp_path: Path, monkeypatch: object) -> None:
    from sfrfr.services import extra_document_intake as edi

    monkeypatch.setattr(edi, "default_unbound_root", lambda: tmp_path / "unbound")
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


def test_unbound_without_token(tmp_path: Path, monkeypatch: object) -> None:
    from sfrfr.services import extra_document_intake as edi
    from sfrfr.services import mail_inbound_documents as mid

    monkeypatch.setattr(edi, "default_unbound_root", lambda: tmp_path / "unbound")
    monkeypatch.setattr(mid, "UnboundMailQueue", edi.UnboundMailQueue)

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
