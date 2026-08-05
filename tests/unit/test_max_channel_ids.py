"""Тесты обнаружения chat_id канала MAX."""

from __future__ import annotations

from pathlib import Path

from sfrfr.integrations.max.channel_ids import list_known, remember_chat_id
from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.handler import handle_max_update

_STORE = Path("var") / "test_max_channel_ids.json"


def _use_store(monkeypatch) -> Path:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    if _STORE.exists():
        _STORE.unlink()
    monkeypatch.setattr(
        "sfrfr.integrations.max.channel_ids.store_path",
        lambda: _STORE,
    )
    return _STORE


def test_remember_and_list(monkeypatch) -> None:
    store = _use_store(monkeypatch)
    entry = remember_chat_id(991122, source="test", update_type="bot_added")
    assert entry is not None
    assert entry["chat_id"] == "991122"
    rows = list_known()
    assert len(rows) == 1
    assert rows[0]["chat_id"] == "991122"
    store.unlink(missing_ok=True)


def test_bot_added_handler_remembers(monkeypatch) -> None:
    store = _use_store(monkeypatch)

    class _Bot(MaxBotClient):
        @property
        def available(self) -> bool:
            return True

    result = handle_max_update(
        {
            "update_type": "bot_added",
            "chat_id": 555001,
            "user_id": 1,
        },
        bot=_Bot(),
    )
    assert result.ok is True
    assert result.action == "bot_added"
    assert "555001" in (result.detail or "")
    assert list_known()[0]["chat_id"] == "555001"
    store.unlink(missing_ok=True)


def test_subscribe_includes_bot_added() -> None:
    import inspect

    src = inspect.getsource(MaxBotClient.subscribe_webhook)
    assert "bot_added" in src
    assert "bot_removed" in src
