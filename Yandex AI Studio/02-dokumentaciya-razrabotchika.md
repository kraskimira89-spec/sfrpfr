# Yandex AI Studio — документация для разработчиков (оглавление)

Источники: [AI Studio docs](https://yandex.cloud/ru/docs/ai-studio/quickstart/) · [OpenAI mode](https://yandex.cloud/ru/docs/ai-studio/concepts/openai) · [SDK](https://aistudio.yandex.ru/docs/ai-studio/sdk/) · [FM API](https://yandex.cloud/ru/docs/foundation-models/api-ref/) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Код: `src/sfrfr` LLM client (Yandex OpenAI-compatible) · env из `.env.example`:

```text
YANDEX_API_KEY=
YANDEX_FOLDER_ID=
YANDEX_MODEL=deepseek-v4-flash/latest
YANDEX_MODEL_CLASSIFY=deepseek-v4-flash
YANDEX_MODEL_ANALYZE=deepseek-v4-flash
YANDEX_MODEL_DRAFT=deepseek-v4-flash
YANDEX_BASE_URL=https://llm.api.cloud.yandex.net/v1
# алиасы LLM_* тоже поддерживаются
```

**Канон runtime SFRFR (2026-09):** classify / analyze / draft / MAX / ops → DeepSeek в Yandex AI Studio (`deepseek-v4-flash`); сверка ИЛС — код.  
`LLMClient` (`src/sfrfr/ai/llm.py`) подменяет YandexGPT на DeepSeek в каталоге YC. Dual-model Lite/Pro — устарело.  
DeepSeek R1 в managed AI Studio нет — используем `deepseek-v4-flash` (см. [блог](https://yandex.cloud/ru/blog/yandex-ai-studio-deepseek-v4-flash)).
---

## Эндпоинты и совместимость

| Тема | Суть | Для SFRFR |
|------|------|-----------|
| Base URL (наш `.env`) | `https://llm.api.cloud.yandex.net/v1` | **P0** — текущий |
| Base URL (часто в новых гайдах) | `https://ai.api.cloud.yandex.net/v1` | **P1** — сверить при апгрейде SDK/доки |
| Auth | API-ключ + `folder_id` (заголовок/параметр модели) | **P0** |
| Model URI | `gpt://<folder_id>/<model>/latest` или короткий id в SDK | **P0** |
| Протокол | OpenAI `chat.completions` (+ stream) | **P0** |
| gRPC/REST native | FM / AI Studio API ref | P1 — если уйдём с OpenAI client |
| Логирование запросов | По умолчанию политики YC; отключать где доступно | **P0** — ПДн |

См. [OpenAI-совместимость](https://yandex.cloud/ru/docs/ai-studio/concepts/openai) · [FM OpenAI](https://yandex.cloud/ru/docs/foundation-models/concepts/openai).

---

## Документация API / операций

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Quickstart](https://yandex.cloud/ru/docs/ai-studio/quickstart/) | Start | Первый вызов | **P0** |
| [Get API key](https://yandex.cloud/ru/docs/ai-studio/operations/get-api-key) | Key | Ключ для сервиса | **P0** |
| [Create prompt](https://yandex.cloud/ru/docs/ai-studio/operations/generation/create-prompt) | Generation op | Параметры генерации | **P0** |
| [Operations hub](https://yandex.cloud/ru/docs/ai-studio/operations/) | How-to index | Все операции | **P0** |
| [Generation concepts](https://yandex.cloud/ru/docs/ai-studio/concepts/generation/) | Models/params | temperature, tokens, models | **P0** |
| [Embeddings](https://yandex.cloud/ru/docs/ai-studio/concepts/embeddings/) | Vectors | RAG | **P1** |
| [Agents](https://yandex.cloud/ru/docs/ai-studio/concepts/agents/) | Agents / Responses | Новый агентный API | **P1** — vs наш CaseOrchestrator |
| [Tools](https://yandex.cloud/ru/docs/ai-studio/tools/) | Tool calling | Function calling | P1 |
| [Tuning](https://yandex.cloud/ru/docs/ai-studio/tuning/) | Fine-tune | Дообучение | **Не для клиентских чатов** |
| [Security](https://yandex.cloud/ru/docs/ai-studio/security/) | Data handling | Что уходит в логи | **P0** |
| [Pricing](https://yandex.cloud/ru/docs/ai-studio/pricing) | Cost | Токены | **P0** |
| [Release notes](https://yandex.cloud/ru/docs/ai-studio/release-notes/) | Changes | Breaking | P1 |
| [FM API ref](https://yandex.cloud/ru/docs/foundation-models/api-ref/) | Low-level API | REST/gRPC | P1 |
| [FM create-prompt](https://yandex.cloud/ru/docs/foundation-models/operations/generation/create-prompt) | Legacy path | Часто тот же контент | P1 |
| [YandexGPT models](https://yandex.cloud/ru/docs/foundation-models/concepts/yandexgpt/) | Model IDs | lite/pro/… | **P0** |

---

## SDK

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [SDK docs](https://aistudio.yandex.ru/docs/ai-studio/sdk/) | Python AIStudio | completions, chat, embeddings, auth auto | **P1** |
| [SDK ref](https://aistudio.yandex.ru/docs/ai-studio/sdk-ref/) | Reference | Полный API SDK | P1 |
| [GitHub yandex-ai-studio-sdk](https://github.com/yandex-cloud/yandex-ai-studio-sdk) | Source | Примеры sync/async, LangChain | P1 |

Пример из SDK (ориентир):

```python
from yandex_ai_studio_sdk import AIStudio
sdk = AIStudio(folder_id="...", auth="<APIKey>")
model = sdk.models.completions("yandexgpt").configure(temperature=0.5)
```

У нас сейчас — OpenAI-compatible HTTP; SDK — кандидат на упрощение auth/retries.

---

## Политика использования в SFRFR (закрепить по доке)

| Правило | Источник в проекте | Дока AI Studio |
|---------|-------------------|----------------|
| LLM: classify / extract / draft | ТЗ-06 | generation · openai |
| Не LLM для сверки ИЛС↔трудовая | ТЗ-06 | — детерминированный код |
| Не LLM как основной OCR | ТЗ-06 / ТЗ-13 | → Vision в `Yandex Cloud/` |
| Маскировать ПДн до модели | ТЗ-06 · security | security |
| Не дообучать на переписках | решение проекта | tuning — skip |
| RAG только обезличенные кейсы | knowledge/ | embeddings |

---

## Карта усиления SFRFR

| Цель | Читать |
|------|--------|
| Стабильный chat.completions | openai · create-prompt · security |
| Сменить/удешевить модель | yandexgpt · pricing · `.env` YANDEX_MODEL |
| Embeddings для RAG | embeddings concepts · SDK text_embeddings |
| Tool calling (поиск по делу) | tools · agents |
| Миграция Assistants→Responses | agents (migration в SDK README) |
| Отключить/ограничить логи промптов | security |

---

## Уже есть у нас

| Тема | Где |
|------|-----|
| OpenAI-compatible клиент | `LLMClient` / Yandex base URL в config |
| Env | `.env.example` `YANDEX_*` / `LLM_*` |
| Политика AI | `docs/specs/06-integrations-and-security.md` |
| Роли → DeepSeek | `LLMClient.for_classify/analyze/draft` · `reason_findings` (канон YC DeepSeek) |
| Инфра отдельно | `Yandex Cloud/` |
| Workspace отдельно | ТЗ-14 |

### Логичные следующие шаги

1. Сверить актуальный **base_url** (`llm.` vs `ai.`) с докой и SDK.  
2. Явно выключить логирование промптов с ПДн (security + headers).  
3. Embeddings для `knowledge/` RAG.  
4. Не включать tuning на клиентских диалогах.
