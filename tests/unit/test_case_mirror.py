"""Тесты зеркала Яндекс.Диск."""

from __future__ import annotations

from sfrfr.integrations.yandex_workspace.case_mirror import (
    mirror_case_document_safe,
    resolve_case_mirror_subfolder,
)
from sfrfr.integrations.yandex_workspace.disk import CASE_SUBFOLDERS, build_case_meta_text


def test_bank_statement_not_mirrored() -> None:
    result = mirror_case_document_safe(
        "case-1", "bank.pdf", b"%PDF", doc_type="bank_statement"
    )
    assert result.get("skipped") is True
    assert result.get("reason") == "bank_statement_no_mirror"


def test_resolve_mirror_subfolder() -> None:
    assert resolve_case_mirror_subfolder(None) == "incoming"
    assert resolve_case_mirror_subfolder("ils") == "incoming"
    assert resolve_case_mirror_subfolder("client_signed_application") == "outgoing"
    assert resolve_case_mirror_subfolder("client_signed_appeal") == "outgoing"
    assert resolve_case_mirror_subfolder("bank_statement") == "incoming"


def test_case_subfolders_whitelist() -> None:
    assert CASE_SUBFOLDERS == frozenset({"incoming", "outgoing", "chat"})


def test_case_meta_text_uses_case_id_only() -> None:
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    text = build_case_meta_text(cid, folder_name="Иванов Иван Иванович")
    assert cid in text
    assert "Иванов Иван Иванович" in text
    assert "incoming" in text
    assert "outgoing" in text
    assert "chat" in text
    low = text.lower()
    assert "снилс" not in low
    assert "телефон" not in low
    assert "phone" not in low


def test_format_case_chat_markdown() -> None:
    from sfrfr.integrations.yandex_workspace.case_mirror import format_case_chat_markdown

    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    md = format_case_chat_markdown(
        cid,
        [
            {
                "author_kind": "client",
                "body": "Здравствуйте",
                "created_at": "2026-09-22T10:00:00+00:00",
            }
        ],
    )
    assert cid in md
    assert "Клиент" in md
    assert "Здравствуйте" in md


def test_chat_export_throttle(monkeypatch) -> None:
    from sfrfr.integrations.yandex_workspace import case_mirror as cm

    calls: list[str] = []

    def _fake_export(case_id: str, *, limit: int = 200, folder_name: str | None = None) -> dict:
        calls.append(case_id)
        return {"ok": True, "case_id": case_id}

    monkeypatch.setattr(cm, "export_case_chat_to_disk_safe", _fake_export)
    cm._last_chat_export_at.clear()
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    first = cm.maybe_export_case_chat_throttled(cid)
    second = cm.maybe_export_case_chat_throttled(cid)
    assert first.get("ok") is True
    assert second.get("skipped") is True
    assert second.get("reason") == "throttled"
    assert calls == [cid]
