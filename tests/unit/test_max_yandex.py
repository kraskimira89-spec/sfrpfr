"""Тесты Yandex LLM-конфига и MAX webhook handler."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sfrfr.ai.llm import LLMClient
from sfrfr.api import create_app
from sfrfr.core.case_store import reset_case_store
from sfrfr.core.config import get_settings
from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.handler import handle_max_update


class _SilentBot(MaxBotClient):
    def __init__(self) -> None:
        self.sent: list[tuple[object, str]] = []

    @property
    def available(self) -> bool:
        return True

    def send_message(  # type: ignore[no-untyped-def,override]
        self,
        *,
        text: str,
        user_id=None,
        chat_id=None,
    ):
        self.sent.append((user_id or chat_id, text))
        return {"ok": True}


def test_llm_yandex_model_uri(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "yandex")
    monkeypatch.setenv("YANDEX_API_KEY", "key")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder123")
    monkeypatch.setenv("YANDEX_MODEL", "yandexgpt/latest")
    get_settings.cache_clear()
    client = LLMClient()
    assert client.available is True
    assert client.model == "gpt://folder123/yandexgpt/latest"
    get_settings.cache_clear()


def test_llm_unavailable_without_folder(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "yandex")
    monkeypatch.setenv("YANDEX_API_KEY", "key")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "")
    get_settings.cache_clear()
    assert LLMClient().available is False
    get_settings.cache_clear()


def test_max_start_and_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    reset_case_store(tmp_path / "cases.json")
    bot = _SilentBot()

    created = handle_max_update(
        {
            "update_type": "message_created",
            "message": {
                "sender": {"user_id": 6407832},
                "recipient": {"chat_id": 382234533, "chat_type": "dialog", "user_id": 6407832},
                "body": {"text": "/start"},
            },
        },
        bot=bot,
    )
    assert created.action == "create"
    assert created.case_id
    assert bot.sent and bot.sent[0][0] == "6407832"

    status = handle_max_update(
        {
            "update_type": "message_created",
            "message": {
                "sender": {"user_id": 6407832},
                "recipient": {"chat_id": 382234533, "chat_type": "dialog", "user_id": 6407832},
                "body": {"text": "/status"},
            },
        },
        bot=bot,
    )
    assert status.action == "status"
    assert status.case_id == created.case_id
    assert any("Этап" in t for _, t in bot.sent)
    get_settings.cache_clear()


def test_max_webhook_endpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_WEBHOOK_SECRET", "sec")
    monkeypatch.setenv("MAX_BOT_TOKEN", "")
    get_settings.cache_clear()
    reset_case_store(tmp_path / "cases.json")

    client = TestClient(create_app())
    forbidden = client.post(
        "/api/integrations/max/webhook",
        json={"user_id": "u2", "chat_id": 1, "text": "/start"},
    )
    assert forbidden.status_code == 403

    ok = client.post(
        "/api/integrations/max/webhook",
        json={"user_id": "u2", "chat_id": 1, "text": "/start"},
        headers={"X-Max-Bot-Api-Secret": "sec"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True
    assert "create" in body["actions"]
    get_settings.cache_clear()
