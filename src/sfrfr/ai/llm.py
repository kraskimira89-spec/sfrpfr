"""Тонкая обёртка над LLM: Yandex AI Studio (по умолчанию) или OpenAI."""

from __future__ import annotations

from typing import Any

from sfrfr.core.config import get_settings


class LLMClient:
    """Chat Completions через OpenAI SDK. Без ключа — заглушка (эвристики агентов)."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = (provider or settings.ai_provider or "yandex").lower()
        self._settings = settings

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
            self.model = model or self._yandex_model_uri(settings)
            if not self.folder_id:
                self.folder_id = self._folder_from_model(self.model)
        else:
            self.api_key = api_key if api_key is not None else settings.openai_api_key
            self.base_url = settings.openai_base_url
            self.folder_id = ""
            self.model = model or settings.openai_model

        self._client: Any | None = None

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
    def _yandex_model_uri(settings: Any) -> str:
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

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        if not self.available:
            return ""
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
