"""Пинг специалистов о сообщении клиента: короткий текст и антидубль."""

from sfrfr.integrations.max.staff_client_ping import (
    build_client_ping,
    reset_staff_ping_cache,
    should_send_ping,
)


def test_same_snippet_is_not_sent_twice() -> None:
    seen: dict[str, str] = {}
    assert should_send_ping(key="u:c", fingerprint="привет", seen=seen)
    assert not should_send_ping(key="u:c", fingerprint="привет", seen=seen)
    assert should_send_ping(key="u:c", fingerprint="другой текст", seen=seen)


def test_ping_text_is_short_and_has_chat_link() -> None:
    url = "https://admin.example/c/abc?view=cases&focus=chat"
    text = build_client_ping(who="MAX 7", snippet="не учли стаж " * 30, staff_url=url)
    assert text.startswith("Сообщение: MAX 7")
    assert url in text
    assert len(text) < 400
    reset_staff_ping_cache()


def test_free_text_pings_staff_once(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from test_max_intake import _msg, _setup

    from sfrfr.integrations.max.handler import handle_max_update

    assert isinstance(tmp_path, Path)
    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("ADMIN_PUBLIC_URL", "https://admin.example")
    from sfrfr.core.config import get_settings

    get_settings.cache_clear()
    sent: list[str] = []
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._fanout_ops_text",
        lambda text, **_k: sent.append(text) or {"ok": True},
    )
    monkeypatch.setattr(
        "sfrfr.services.lead_ops_notify.notify_ops_new_lead",
        lambda **_k: {"ok": True},
    )
    reset_staff_ping_cache()
    handle_max_update(_msg(41, "/start"), bot=bot)
    handle_max_update(_msg(41, "не учли стаж, вот телефон"), bot=bot)
    handle_max_update(_msg(41, "не учли стаж, вот телефон"), bot=bot)
    assert len(sent) == 1
    assert "не учли стаж" in sent[0]
    assert "focus=chat" in sent[0] or "/c/" in sent[0]
    reset_staff_ping_cache()
