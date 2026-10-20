"""SFRFR-81: нет «получили» без байтов; lifecycle; staff open local-pending."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_max_intake import _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import attachment_lifecycle as life
from sfrfr.integrations.max import document_background as bg
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.ops import chat_bot_metrics as metrics
from sfrfr.services.document_upload import is_document_downloadable
from sfrfr.services.file_security import is_downloadable_status

USER = "902"


def _file_without_url(user_id: int | str, *, mid: str = "mid-1") -> dict:
    return {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": int(user_id)},
            "recipient": {"chat_id": 1, "chat_type": "dialog"},
            "body": {
                "mid": mid,
                "text": "",
                "attachments": [
                    {
                        "type": "file",
                        "payload": {
                            "token": "tok-without-url",
                            "file_name": "scan.pdf",
                        },
                    }
                ],
            },
        },
    }


@pytest.fixture(autouse=True)
def _reset_life(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "storage"
    root.mkdir()
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(root / "uploads"))
    (root / "uploads").mkdir()
    get_settings.cache_clear()
    life.reset_for_tests()
    bg.reset_quiet_state()
    yield
    life.reset_for_tests()
    bg.reset_quiet_state()
    get_settings.cache_clear()


def test_media_without_url_no_got_documents_ack(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    bot.sent.clear()
    out = handle_max_update(_file_without_url(USER), bot=bot)
    low = (out.reply or "").lower()
    assert "получил" not in low
    assert "документы получили" not in low
    assert out.action in {
        "upload_media_checking",
        "upload_media_failed",
        "upload_media_pending",
    }
    if out.reply:
        assert (
            "провер" in low
            or "повтор" in low
            or "ещё раз" in low
            or "еще раз" in low
            or "вижу" in low
        )


def test_burst_without_url_no_false_got_ack(tmp_path: Path, monkeypatch) -> None:
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    bot.sent.clear()
    for i in range(3):
        handle_max_update(_file_without_url(USER, mid=f"mid-{i}"), bot=bot)
    for _u, t in bot.sent:
        low = (t or "").lower()
        assert "документы получили" not in low
        assert "мне нужно немного времени" not in low


def test_failed_download_registers_retry_then_exhaust(
    tmp_path: Path, monkeypatch
) -> None:
    life.reset_for_tests()
    job = life.enqueue_awaiting_bytes(
        user_id=USER,
        case_id="c1",
        message_mid="m1",
        attach_key="url:abc",
        filename="a.pdf",
        url="https://example.invalid/file.pdf",
        chat_id=1,
    )
    assert job["stage"] == "awaiting_bytes"
    # исчерпать попытки
    for _ in range(life.MAX_ATTEMPTS):
        job = life.mark_attempt_failed(job["id"], error_code="download_error")
    assert job["stage"] == "failed"
    assert job["error_code"] == "download_error"


def test_dedupe_same_attachment_one_job() -> None:
    life.reset_for_tests()
    a = life.enqueue_awaiting_bytes(
        user_id=USER,
        case_id="c1",
        message_mid="m1",
        attach_key="tok:xx",
        filename="a.pdf",
        url=None,
        chat_id=1,
    )
    b = life.enqueue_awaiting_bytes(
        user_id=USER,
        case_id="c1",
        message_mid="m1",
        attach_key="tok:xx",
        filename="a.pdf",
        url=None,
        chat_id=1,
    )
    assert a["id"] == b["id"]
    assert len(life.list_jobs()) == 1


def test_needs_reupload_with_local_path_downloadable_for_staff() -> None:
    assert is_downloadable_status("needs_reupload") is False
    row = {
        "ingest_status": "needs_reupload",
        "antivirus_status": "not_configured",
        "local_path": "quarantine/c/d/f.pdf",
    }
    assert is_document_downloadable(row, allow_local_pending=True) is True


def test_false_ack_metric_zero_on_media_without_bytes(
    tmp_path: Path, monkeypatch
) -> None:
    before = metrics.MAX_FALSE_ACK_TOTAL._value.get()  # type: ignore[attr-defined]
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    bot.sent.clear()
    handle_max_update(_file_without_url(USER), bot=bot)
    after = metrics.MAX_FALSE_ACK_TOTAL._value.get()  # type: ignore[attr-defined]
    assert after == before


def test_lifecycle_journal_has_no_secrets() -> None:
    life.reset_for_tests()
    job = life.enqueue_awaiting_bytes(
        user_id=USER,
        case_id="c1",
        message_mid="m1",
        attach_key="tok:secret-token-value",
        filename="a.pdf",
        url="https://cdn.example/secret-path/file.pdf?sig=abc",
        chat_id=1,
    )
    entry = life.journal_entry(job)
    blob = str(entry)
    assert "secret-token" not in blob
    assert "sig=abc" not in blob
    assert "https://" not in blob
    assert entry.get("stage")
    assert "attach_id" in entry
