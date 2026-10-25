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


def _prod_reserve_env(monkeypatch: pytest.MonkeyPatch, *, until: str) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEEPSEEK_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_FALLBACK_PROD_UNTIL", until)
    get_settings.cache_clear()


def test_prod_reserve_only_for_depersonalized_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prod_reserve_env(monkeypatch, until="2099-01-01")

    assert LLMClient(provider="yandex")._fallback_client() is None
    fb = LLMClient(provider="yandex", foreign_ok=True)._fallback_client()
    assert fb is not None and fb.provider == "deepseek" and fb.available is True
    get_settings.cache_clear()


def test_prod_reserve_off_after_until_date(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_reserve_env(monkeypatch, until="2000-01-01")

    assert LLMClient(provider="yandex", foreign_ok=True)._fallback_client() is None
    get_settings.cache_clear()


def test_prod_reserve_off_without_until_date(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_reserve_env(monkeypatch, until="")

    assert LLMClient(provider="yandex", foreign_ok=True)._fallback_client() is None
    get_settings.cache_clear()
