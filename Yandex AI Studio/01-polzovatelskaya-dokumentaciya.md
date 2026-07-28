# Yandex AI Studio — пользовательская / консольная документация (оглавление)

Источники: [AI Studio UI](https://aistudio.yandex.ru/) · [Docs AI Studio](https://yandex.cloud/ru/docs/ai-studio/quickstart/) · [Service page](https://yandex.cloud/ru/services/ai-studio) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Наш стек: OpenAI-compatible → `YANDEX_BASE_URL` / `LLM_BASE_URL` · модель `YANDEX_MODEL` · ключ `YANDEX_API_KEY` + `YANDEX_FOLDER_ID`.

> Cloud-инфра (VM/PG/Storage) — в папке **`Yandex Cloud/`**.  
> Почта/Телемост — **ТЗ-14**, не AI Studio.

---

## Как пользоваться

| Приоритет | Смысл |
|-----------|--------|
| **P0** | Ключ, каталог, генерация текста, тариф, безопасность логов |
| **P1** | Embeddings/RAG, agents, tuning, UI Studio |
| **P2** | Image gen, Search API, IDE-плагины |

---

## Продукт и старт в UI

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [AI Studio (сайт)](https://aistudio.yandex.ru/) | Web UI | Промпты, модели, эксперименты | **P0** — ручные тесты промптов |
| [О сервисе](https://yandex.cloud/ru/services/ai-studio) | Описание | Возможности платформы | **P0** |
| [Quickstart](https://yandex.cloud/ru/docs/ai-studio/quickstart/) | Быстрый старт | Первый запрос к модели | **P0** |
| [Получить API-ключ](https://yandex.cloud/ru/docs/ai-studio/operations/get-api-key) | Ключ для Studio | Выпуск ключа под AI | **P0** |
| [Создать промпт](https://yandex.cloud/ru/docs/ai-studio/operations/generation/create-prompt) | Операция | Промпт в консоли/API | **P0** — classifier/drafter |
| [Операции (хаб)](https://yandex.cloud/ru/docs/ai-studio/operations/) | How-to | Список практических статей | **P0** |
| [Тарифы](https://yandex.cloud/ru/docs/ai-studio/pricing) | Pricing | Стоимость токенов/моделей | **P0** — бюджет LLM |
| [Безопасность](https://yandex.cloud/ru/docs/ai-studio/security/) | Security | Логирование, доступы, ПДн | **P0** — маскирование до LLM |
| [Release notes](https://yandex.cloud/ru/docs/ai-studio/release-notes/) | Changelog | Новые модели/API | P1 |

---

## Концепции для оператора/продакта

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Генерация текста](https://yandex.cloud/ru/docs/ai-studio/concepts/generation/) | Completions | Модели, параметры, режимы | **P0** |
| [OpenAI-совместимость](https://yandex.cloud/ru/docs/ai-studio/concepts/openai) | OpenAI API | base_url + chat.completions | **P0** — наш `LLMClient` |
| [Embeddings](https://yandex.cloud/ru/docs/ai-studio/concepts/embeddings/) | Vectors | Эмбеддинги для поиска | **P1** — RAG knowledge |
| [Agents](https://yandex.cloud/ru/docs/ai-studio/concepts/agents/) | Agents | Агентный контур / Responses | **P1** — сравнить с нашим оркестратором |
| [Tools](https://yandex.cloud/ru/docs/ai-studio/tools/) | Tools | Инструменты моделей | P1 |
| [Tuning](https://yandex.cloud/ru/docs/ai-studio/tuning/) | Fine-tune | Дообучение | **P2** — решение: **не** дообучать на переписках |
| [YandexGPT (FM)](https://yandex.cloud/ru/docs/foundation-models/concepts/yandexgpt/) | Семейство GPT | Pro/Lite и URI моделей | **P0** |
| [FM embeddings](https://yandex.cloud/ru/docs/foundation-models/concepts/embeddings/) | Embeddings (legacy path) | text-search-* | **P1** |
| [FM OpenAI](https://yandex.cloud/ru/docs/foundation-models/concepts/openai) | OpenAI (FM docs) | Дубль/редирект концепта | P1 |
| [FM pricing](https://yandex.cloud/ru/docs/foundation-models/pricing) | Цены FM | Если URL ещё жив | P1 |
| [FM security](https://yandex.cloud/ru/docs/foundation-models/security/) | Security FM | Политика данных | **P0** |

---

## SDK / UI для разработчика-человека

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [SDK overview](https://aistudio.yandex.ru/docs/ai-studio/sdk/) | Python SDK | Высокоуровневый клиент | **P1** — опционально вместо raw OpenAI |
| [SDK reference](https://aistudio.yandex.ru/docs/ai-studio/sdk-ref/) | API ref SDK | Классы/методы | P1 |
| [GitHub SDK](https://github.com/yandex-cloud/yandex-ai-studio-sdk) | Репозиторий | Примеры, changelog SDK | P1 |
| [Туториал IDE](https://yandex.cloud/ru/docs/tutorials/ml-ai/) | VS Code / Roo | Подключение Compatible API | P2 — локальная разработка |

---

## Быстрый указатель под SFRFR

| Задача | Смотреть |
|--------|----------|
| Выпустить ключ + folder для LLM | get-api-key · Cloud IAM (см. Yandex Cloud) |
| Проверить chat.completions | concepts/openai · create-prompt · AI Studio UI |
| Урезать логирование ПДн в модели | security · заголовки/настройки логирования |
| RAG по knowledge/cases | embeddings · (не складывать сырые ПДн) |
| Не дообучать на чатах клиентов | tuning — осознанно **не** трогать |
| Сверить модель в `.env` | yandexgpt concepts · pricing |
