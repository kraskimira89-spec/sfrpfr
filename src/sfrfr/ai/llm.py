"""Тонкая обёртка над LLM: Yandex AI Studio (основной) + DeepSeek platform (запасной)."""

from __future__ import annotations

import logging
from typing import Any, Literal

from sfrfr.core.config import get_settings

LlmPurpose = Literal["default", "classify", "analyze", "draft"]
logger = logging.getLogger(__name__)


class LLMClient:
    """Chat Completions через OpenAI SDK. Без ключа — заглушка (эвристики агентов)."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        purpose: LlmPurpose = "default",
        allow_fallback: bool = True,
    ) -> None:
        settings = get_settings()
        self.provider = (provider or settings.ai_provider or "yandex").lower()
        self._settings = settings
        self.purpose: LlmPurpose = purpose
        self.allow_fallback = allow_fallback

        if self.provider == "yandex":
            self.api_key = api_key if api_key is not None else (
                settings.yandex_api_key.strip() or settings.llm_api_key.strip()
            )
            self.base_url = (
                settings.yandex_base_url.strip()
                or settings.llm_base_url.strip()
                or "https://llm.api.cloud.yandex.net/v1"
            )
            self.folder_id = (
                settings.yandex_folder_id.strip() or settings.llm_folder_id.strip()
            )
            self.model = model or self._yandex_model_uri(settings, purpose=purpose)
            if not self.folder_id:
                self.folder_id = self._folder_from_model(self.model)
        elif self.provider == "deepseek":
            self.api_key = api_key if api_key is not None else settings.deepseek_api_key.strip()
            self.base_url = (
                settings.deepseek_base_url.strip() or "https://api.deepseek.com"
            ).rstrip("/")
            self.folder_id = ""
            self.model = model or (settings.deepseek_model.strip() or "deepseek-chat")
        else:
            self.api_key = api_key if api_key is not None else settings.openai_api_key
            self.base_url = settings.openai_base_url
            self.folder_id = ""
            self.model = model or settings.openai_model

        self._client: Any | None = None

    @classmethod
    def for_classify(cls, **kwargs: Any) -> LLMClient:
        return cls(purpose="classify", **kwargs)

    @classmethod
    def for_analyze(cls, **kwargs: Any) -> LLMClient:
        return cls(purpose="analyze", **kwargs)

    @classmethod
    def for_draft(cls, **kwargs: Any) -> LLMClient:
        return cls(purpose="draft", **kwargs)

    @classmethod
    def for_deepseek_fallback(cls, *, purpose: LlmPurpose = "analyze") -> LLMClient:
        """Прямой клиент platform.deepseek.com без вложенного fallback."""
        return cls(provider="deepseek", purpose=purpose, allow_fallback=False)

    @staticmethod
    def _folder_from_model(model: str) -> str:
        # gpt://<folder_id>/<model>
        text = (model or "").strip()
        if not text.startswith("gpt://"):
            return ""
        rest = text[len("gpt://") :]
        folder, _, _tail = rest.partition("/")
        return folder.strip()

    @staticmethod
    def _yandex_model_uri(settings: Any, *, purpose: LlmPurpose = "default") -> str:
        purpose_model = ""
        if purpose == "classify":
            purpose_model = (settings.yandex_model_classify or "").strip()
        elif purpose == "analyze":
            purpose_model = (settings.yandex_model_analyze or "").strip()
        elif purpose == "draft":
            purpose_model = (settings.yandex_model_draft or "").strip()

        # Для ролей classify/analyze/draft — сначала роль-модель; иначе общий fallback.
        # LLM_MODEL (полный gpt://) не должен перекрывать роль, если роль задана.
        if purpose_model:
            model = purpose_model
        else:
            model = (settings.llm_model or settings.yandex_model or "").strip()

        if model.startswith("gpt://"):
            return model
        folder = (settings.yandex_folder_id or settings.llm_folder_id or "").strip()
        if not folder:
            return model or "yandexgpt/latest"
        return f"gpt://{folder}/{model.lstrip('/')}"

    @property
    def available(self) -> bool:
        if self.provider == "yandex":
            # folder можно взять из gpt://… в model
            return bool(self.api_key and (self.folder_id or self.model.startswith("gpt://")))
        return bool(self.api_key)

    def _fallback_client(self) -> LLMClient | None:
        if not self.allow_fallback:
            return None
        if self.provider == "deepseek":
            return None
        settings = self._settings
        if not settings.deepseek_fallback_enabled:
            return None
        if not settings.deepseek_api_key.strip():
            return None
        return LLMClient.for_deepseek_fallback(purpose=self.purpose)

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    'Установите AI-зависимости: pip install -e ".[ai]"'
                ) from exc
            headers: dict[str, str] = {}
            if self.provider == "yandex" and self.folder_id:
                headers["x-folder-id"] = self.folder_id
                # ПДн: по возможности не логировать содержимое на стороне провайдера
                headers["x-data-logging-enabled"] = "false"
            kwargs: dict[str, Any] = {
                "api_key": self.api_key,
                "base_url": self.base_url,
            }
            if headers:
                kwargs["default_headers"] = headers
            self._client = OpenAI(**kwargs)
        return self._client

    def _chat_once(self, *, system: str, user: str, temperature: float) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        fallback = self._fallback_client()
        if not self.available:
            if fallback is not None and fallback.available:
                logger.warning(
                    "LLM primary unavailable (provider=%s); using DeepSeek fallback",
                    self.provider,
                )
                return fallback.chat(system=system, user=user, temperature=temperature)
            return ""
        try:
            return self._chat_once(system=system, user=user, temperature=temperature)
        except Exception as exc:  # noqa: BLE001 — запасной провайдер при сбое основного
            if fallback is None or not fallback.available:
                raise
            logger.warning(
                "LLM primary failed (provider=%s purpose=%s): %s; using DeepSeek fallback",
                self.provider,
                self.purpose,
                exc,
            )
            return fallback.chat(system=system, user=user, temperature=temperature)
