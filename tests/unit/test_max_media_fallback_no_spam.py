"""Медиа без url не должно спамить FALLBACK_MENU на каждый файл."""

from __future__ import annotations

from pathlib import Path

from test_max_intake import _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import document_background as bg
from sfrfr.integrations.max.attachments import has_media_attachments
from sfrfr.integrations.max.handler import handle_max_update

USER = "901"


def _file_update_without_url(user_id: int | str) -> dict:
    return {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": int(user_id)},
            "recipient": {"chat_id": 1, "chat_type": "dialog"},
            "body": {
                "text": "",
                "attachments": [
                    {
                        "type": "file",
                        "payload": {"token": "tok-without-url", "file_name": "scan.pdf"},
                    }
                ],
            },
        },
    }


def test_has_media_without_url() -> None:
    assert has_media_attachments(_file_update_without_url(1)) is True


def test_burst_media_without_url_one_calm_ack(tmp_path: Path, monkeypatch) -> None:
    bg.reset_quiet_state()
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    bot.sent.clear()

    actions = []
    for _ in range(5):
        out = handle_max_update(_file_update_without_url(USER), bot=bot)
        actions.append(out.action)

    client_texts = [t for _u, t in bot.sent if t]
    assert len(client_texts) == 1
    low = client_texts[0].lower()
    assert "обработ" in low or "время" in low or "разбор" in low
    assert "напиш" in low
    assert "спасибо за сообщение" not in low
    assert "как получить" not in low
    assert "заказать звонок" not in low
    assert actions[0] == "upload_media_pending"
    assert actions[1:] == ["upload_media_quiet"] * 4
    get_settings.cache_clear()


def test_empty_update_without_media_markers_still_calm_ack(
    tmp_path: Path, monkeypatch
) -> None:
    """Как на проде: пустой апдейт без url → calm ack, не FALLBACK_MENU."""
    bg.reset_quiet_state()
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    bot.sent.clear()
    empty = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": int(USER)},
            "recipient": {"chat_id": 1, "chat_type": "dialog"},
            "body": {"text": ""},
        },
    }
    out = handle_max_update(empty, bot=bot)
    assert out.action == "ack_processing"
    low = (out.reply or "").lower()
    assert "время" in low or "обработ" in low or "разбор" in low
    assert "спасибо за сообщение" not in low
    assert "кнопками ниже" not in low
    get_settings.cache_clear()


def test_claim_processing_ack_atomic_under_threads() -> None:
    import threading

    bg.reset_quiet_state()
    results: list[bool] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()
        results.append(bg.claim_processing_ack("u-claim", case_id="c1"))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1
    assert results.count(False) == 7
