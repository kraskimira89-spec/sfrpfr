from __future__ import annotations

import pytest

from sfrfr.ai.llm import LLMClient
from sfrfr.core.config import get_settings


def test_foreign_llm_is_unavailable_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    get_settings.cache_clear()

    client = LLMClient(provider="deepseek", allow_fallback=False)

    assert client.available is False
    get_settings.cache_clear()


def test_deepseek_fallback_is_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEEPSEEK_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    get_settings.cache_clear()

    client = LLMClient(provider="yandex")

    assert client._fallback_client() is None
    get_settings.cache_clear()
