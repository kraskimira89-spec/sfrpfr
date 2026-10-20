"""Медиа без url не спамит FALLBACK и не врёт «документы получили»."""

from __future__ import annotations

from pathlib import Path

from test_max_intake import _msg, _setup

from sfrfr.core.config import get_settings
from sfrfr.integrations.max import attachment_lifecycle as life
from sfrfr.integrations.max import document_background as bg
from sfrfr.integrations.max.attachments import has_media_attachments
from sfrfr.integrations.max.handler import handle_max_update

USER = "901"


def _file_update_without_url(user_id: int | str, *, mid: str = "mid-x") -> dict:
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
                        "payload": {"token": "tok-without-url", "file_name": "scan.pdf"},
                    }
                ],
            },
        },
    }


def test_has_media_without_url() -> None:
    assert has_media_attachments(_file_update_without_url(1)) is True


def test_burst_media_without_url_one_honest_reply(tmp_path: Path, monkeypatch) -> None:
    bg.reset_quiet_state()
    life.reset_for_tests()
    bot = _setup(tmp_path, monkeypatch)
    handle_max_update(_msg(USER, "/start"), bot=bot)
    bot.sent.clear()

    actions = []
    for i in range(5):
        out = handle_max_update(_file_update_without_url(USER, mid=f"m-{i}"), bot=bot)
        actions.append(out.action)

    client_texts = [t for _u, t in bot.sent if t]
    assert len(client_texts) == 1
    low = client_texts[0].lower()
    assert "документы получили" not in low
    assert "мне нужно немного времени" not in low
    assert "спасибо за сообщение" not in low
    assert "заказать звонок" not in low
    assert (
        "провер" in low
        or "повтор" in low
        or "ещё раз" in low
        or "еще раз" in low
        or "вижу" in low
    )
    assert actions[0] in {"upload_media_checking", "upload_media_failed"}
    assert all(a in {actions[0], "upload_media_quiet"} for a in actions[1:])
    get_settings.cache_clear()


def test_empty_update_without_media_no_false_docs_ack(
    tmp_path: Path, monkeypatch
) -> None:
    """Пустой апдейт без медиа — не выдаём «документы получили»."""
    bg.reset_quiet_state()
    life.reset_for_tests()
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
    assert out.action == "empty_noop"
    assert "получил" not in (out.reply or "").lower()
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
