"""Тонкая обёртка над LLM: Yandex AI Studio; иностранный fallback только вне production.

Perplexity Router (`AI_PROVIDER=perplexity`): OpenAI SDK →
`https://api.perplexity.ai/router/v1` + `PERPLEXITY_API_KEY`. Не Perplexity SDK.
Slug моделей только из GET /router/v1/models (allowlist ключа).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from sfrfr.core.config import get_settings

LlmPurpose = Literal["default", "classify", "analyze", "draft"]
logger = logging.getLogger(__name__)

# Канон Router OpenAI-compatible base (SDK дописывает /chat/completions).
PERPLEXITY_ROUTER_BASE_URL = "https://api.perplexity.ai/router/v1"


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
        elif self.provider in {"perplexity", "perplexity_router", "pplx"}:
            self.provider = "perplexity"
            self.api_key = (
                api_key
                if api_key is not None
                else settings.perplexity_api_key.strip()
            )
            raw_base = (
                settings.perplexity_base_url.strip() or PERPLEXITY_ROUTER_BASE_URL
            )
            self.base_url = raw_base.rstrip("/")
            self.folder_id = ""
            self.model = model or self._perplexity_model(settings, purpose=purpose)
        else:
            self.api_key = api_key if api_key is not None else settings.openai_api_key
            self.base_url = settings.openai_base_url
            self.folder_id = ""
            self.model = model or settings.openai_model

        self._client: Any | None = None
        self._perplexity_resolved_model: str | None = None

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
    def for_ops_dialog(cls, **kwargs: Any) -> LLMClient:
        """Диалог специалистов в MAX Ops: Yandex AI Studio DeepSeek (не platform.deepseek.com)."""
        settings = get_settings()
        short = (kwargs.pop("model", None) or settings.max_ops_llm_model or "").strip()
        if not short:
            short = (settings.yandex_model_analyze or "").strip() or "deepseek-v4-flash"
        if short.startswith("gpt://"):
            model = short
        else:
            folder = (settings.yandex_folder_id or settings.llm_folder_id or "").strip()
            model = f"gpt://{folder}/{short.lstrip('/')}" if folder else short
        return cls(
            provider="yandex",
            model=model,
            purpose="analyze",
            allow_fallback=False,
            **kwargs,
        )

    @classmethod
    def for_deepseek_fallback(cls, *, purpose: LlmPurpose = "analyze") -> LLMClient:
        """Прямой клиент platform.deepseek.com без вложенного fallback."""
        return cls(provider="deepseek", purpose=purpose, allow_fallback=False)

    @classmethod
    def for_perplexity(cls, **kwargs: Any) -> LLMClient:
        """Perplexity Router (OpenAI Chat Completions)."""
        return cls(provider="perplexity", allow_fallback=False, **kwargs)

    @staticmethod
    def _perplexity_model(settings: Any, *, purpose: LlmPurpose = "default") -> str:
        purpose_model = ""
        if purpose == "classify":
            purpose_model = (settings.perplexity_model_classify or "").strip()
        elif purpose == "analyze":
            purpose_model = (settings.perplexity_model_analyze or "").strip()
        elif purpose == "draft":
            purpose_model = (settings.perplexity_model_draft or "").strip()
        if purpose_model:
            return purpose_model
        return (settings.perplexity_model or "").strip()

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
    def _prefer_yc_deepseek(model: str, settings: Any) -> str:
        """YandexGPT в каталоге не используем: канон — DeepSeek в Yandex AI Studio."""
        raw = (model or "").strip()
        lower = raw.lower()
        if "deepseek" in lower:
            return raw
        ds = (settings.yandex_model_analyze or "").strip() or "deepseek-v4-flash"
        if ds.startswith("gpt://"):
            return ds
        if "yandexgpt" in lower or not raw:
            if raw.startswith("gpt://"):
                folder = LLMClient._folder_from_model(raw)
                if folder:
                    return f"gpt://{folder}/{ds.lstrip('/')}"
            return ds
        return raw

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

        model = LLMClient._prefer_yc_deepseek(model, settings)

        if model.startswith("gpt://"):
            return model
        folder = (settings.yandex_folder_id or settings.llm_folder_id or "").strip()
        if not folder:
            return model or "deepseek-v4-flash"
        return f"gpt://{folder}/{model.lstrip('/')}"

    @property
    def available(self) -> bool:
        # ПДн в production — только Yandex AI Studio (не Perplexity / OpenAI / DeepSeek).
        if (
            self._settings.app_env.strip().lower() in {"prod", "production"}
            and self.provider != "yandex"
        ):
            return False
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
        if settings.app_env.strip().lower() in {"prod", "production"}:
            return None
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

    def _resolve_chat_model(self) -> str:
        """Для Perplexity — slug только из каталога ключа (GET /models), без выдуманных id."""
        if self.provider != "perplexity":
            return self.model
        if self.model.strip():
            return self.model.strip()
        if self._perplexity_resolved_model:
            return self._perplexity_resolved_model
        client = self._get_client()
        listed = client.models.list()
        data = getattr(listed, "data", None) or []
        if not data:
            raise RuntimeError(
                "Perplexity Router: пустой каталог GET /models — "
                "проверьте доступ к Router (private preview) и PERPLEXITY_API_KEY"
            )
        first_id = str(getattr(data[0], "id", "") or "").strip()
        if not first_id:
            raise RuntimeError("Perplexity Router: у первой модели в каталоге нет id")
        self._perplexity_resolved_model = first_id
        logger.info("perplexity router: model from catalog id=%s", first_id)
        return first_id

    def _chat_once(self, *, system: str, user: str, temperature: float) -> str:
        client = self._get_client()
        model = self._resolve_chat_model()
        resp = client.chat.completions.create(
            model=model,
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
