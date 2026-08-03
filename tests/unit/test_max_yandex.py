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
        attachments=None,
    ):
        self.sent.append((user_id or chat_id, text))
        return {"ok": True}


def test_llm_yandex_model_uri(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "yandex")
    monkeypatch.setenv("YANDEX_API_KEY", "key")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder123")
    monkeypatch.setenv("YANDEX_MODEL", "yandexgpt/latest")
    monkeypatch.setenv("YANDEX_MODEL_CLASSIFY", "")
    monkeypatch.setenv("YANDEX_MODEL_ANALYZE", "")
    monkeypatch.setenv("YANDEX_MODEL_DRAFT", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_FOLDER_ID", "")
    monkeypatch.setenv("LLM_MODEL", "")
    get_settings.cache_clear()
    client = LLMClient()
    assert client.available is True
    assert client.model == "gpt://folder123/yandexgpt/latest"
    get_settings.cache_clear()


def test_llm_dual_model_purposes(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "yandex")
    monkeypatch.setenv("YANDEX_API_KEY", "key")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder123")
    monkeypatch.setenv("YANDEX_MODEL", "yandexgpt/latest")
    monkeypatch.setenv("YANDEX_MODEL_CLASSIFY", "yandexgpt-lite/latest")
    monkeypatch.setenv("YANDEX_MODEL_ANALYZE", "deepseek-v4-flash")
    monkeypatch.setenv("YANDEX_MODEL_DRAFT", "yandexgpt/latest")
    monkeypatch.setenv("LLM_MODEL", "gpt://folder123/yandexgpt-lite/latest")
    get_settings.cache_clear()
    assert LLMClient.for_classify().model == "gpt://folder123/yandexgpt-lite/latest"
    assert LLMClient.for_analyze().model == "gpt://folder123/deepseek-v4-flash"
    assert LLMClient.for_draft().model == "gpt://folder123/yandexgpt/latest"
    get_settings.cache_clear()


def test_llm_unavailable_without_folder(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "yandex")
    monkeypatch.setenv("YANDEX_API_KEY", "key")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "")
    monkeypatch.setenv("YANDEX_MODEL", "yandexgpt/latest")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_FOLDER_ID", "")
    monkeypatch.setenv("LLM_MODEL", "")
    get_settings.cache_clear()
    assert LLMClient().available is False
    get_settings.cache_clear()


def test_llm_uses_llm_aliases(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "yandex")
    monkeypatch.setenv("YANDEX_API_KEY", "")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("LLM_FOLDER_ID", "llm-folder")
    monkeypatch.setenv("LLM_MODEL", "gpt://llm-folder/yandexgpt-lite/latest")
    get_settings.cache_clear()
    client = LLMClient()
    assert client.available is True
    assert client.api_key == "llm-key"
    assert client.folder_id == "llm-folder"
    assert client.model == "gpt://llm-folder/yandexgpt-lite/latest"
    get_settings.cache_clear()


def test_llm_deepseek_provider(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    get_settings.cache_clear()
    client = LLMClient()
    assert client.provider == "deepseek"
    assert client.available is True
    assert client.api_key == "sk-test"
    assert client.model == "deepseek-chat"
    get_settings.cache_clear()


def test_llm_deepseek_fallback_when_primary_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "yandex")
    monkeypatch.setenv("YANDEX_API_KEY", "")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_FOLDER_ID", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-fallback")
    monkeypatch.setenv("DEEPSEEK_FALLBACK_ENABLED", "1")
    get_settings.cache_clear()
    primary = LLMClient(purpose="analyze")
    assert primary.available is False
    fb = primary._fallback_client()
    assert fb is not None
    assert fb.provider == "deepseek"
    assert fb.available is True

    called: dict[str, str] = {}

    def _fake_chat(*, system: str, user: str, temperature: float = 0.0) -> str:
        called["system"] = system
        return "fallback-ok"

    assert fb is not None
    fb.chat = _fake_chat  # type: ignore[method-assign]
    # подмена fallback-клиента
    monkeypatch.setattr(primary, "_fallback_client", lambda: fb)
    out = primary.chat(system="sys", user="user")
    assert out == "fallback-ok"
    assert called["system"] == "sys"
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
    assert any("Документов" in t for _, t in bot.sent)
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
