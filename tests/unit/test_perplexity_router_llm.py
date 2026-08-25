"""Perplexity Router как AI_PROVIDER в LLMClient (без живого API)."""

from __future__ import annotations

import pytest

from sfrfr.ai.llm import PERPLEXITY_ROUTER_BASE_URL, LLMClient
from sfrfr.core.config import get_settings


def test_perplexity_provider_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("AI_PROVIDER", "perplexity")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    monkeypatch.setenv("PERPLEXITY_BASE_URL", PERPLEXITY_ROUTER_BASE_URL)
    monkeypatch.setenv("PERPLEXITY_MODEL", "perplexity/kimi-k3")
    get_settings.cache_clear()

    client = LLMClient()
    assert client.provider == "perplexity"
    assert client.available is True
    assert client.api_key == "pplx-test"
    assert client.base_url == PERPLEXITY_ROUTER_BASE_URL
    assert client.model == "perplexity/kimi-k3"
    assert client.folder_id == ""
    get_settings.cache_clear()


def test_perplexity_purpose_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("AI_PROVIDER", "perplexity")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    monkeypatch.setenv("PERPLEXITY_MODEL", "perplexity/kimi-k3")
    monkeypatch.setenv("PERPLEXITY_MODEL_CLASSIFY", "perplexity/deepseek-v4-flash-0731")
    get_settings.cache_clear()

    assert LLMClient.for_classify().model == "perplexity/deepseek-v4-flash-0731"
    assert LLMClient.for_analyze().model == "perplexity/kimi-k3"
    get_settings.cache_clear()


def test_perplexity_unavailable_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    get_settings.cache_clear()

    client = LLMClient(provider="perplexity", allow_fallback=False)
    assert client.available is False
    get_settings.cache_clear()


def test_for_perplexity_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    monkeypatch.setenv("PERPLEXITY_MODEL", "perplexity/glm-5.2")
    get_settings.cache_clear()

    client = LLMClient.for_perplexity(purpose="draft")
    assert client.provider == "perplexity"
    assert client.purpose == "draft"
    assert client.allow_fallback is False
    assert client.model == "perplexity/glm-5.2"
    get_settings.cache_clear()
