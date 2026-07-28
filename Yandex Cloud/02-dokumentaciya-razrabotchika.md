# Yandex Cloud — документация для разработчиков (оглавление)

Источники: [Docs](https://yandex.cloud/ru/docs/) · [Overview API](https://yandex.cloud/ru/docs/overview/api) · [SDK](https://yandex.cloud/ru/docs/overview/sdk) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Код/конфиг: `.env` `YANDEX_*` · ТЗ-15 · Vision/OCR · будущий self-hosted Supabase.

> LLM/OpenAI-совместимый чат — подробно в **`Yandex AI Studio/`**. Здесь — инфра, IAM, Storage, Captcha, Vision.

---

## Платформенные API / SDK

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Обзор API](https://yandex.cloud/ru/docs/overview/api) | Service APIs | Карта REST/gRPC сервисов | **P0** |
| [Обзор SDK](https://yandex.cloud/ru/docs/overview/sdk) | Cloud SDK | Официальные SDK | P1 |
| [CLI](https://yandex.cloud/ru/docs/cli/quickstart) | yc | Автоматизация деплоя | **P1** |
| [IAM API-ключ](https://yandex.cloud/ru/docs/iam/concepts/authorization/api-key) | Auth | Статичный ключ + scope сервисов | **P0** |
| [IAM-токен](https://yandex.cloud/ru/docs/iam/concepts/authorization/iam-token) | Short-lived | Обмен OAuth→IAM | P1 |
| [Сервисный аккаунт](https://yandex.cloud/ru/docs/iam/operations/sa/create) | SA | Роли на folder | **P0** |

---

## Compute / сеть / данные (целевой контур)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Compute](https://yandex.cloud/ru/docs/compute/) | VM API/ops | Диски, образы, группы | **P1** |
| [VPC](https://yandex.cloud/ru/docs/vpc/) | Network API | SG, NAT, маршруты | **P1** |
| [Managed PostgreSQL](https://yandex.cloud/ru/docs/managed-postgresql/) | MPG API | Кластеры, бэкапы, users | **P1** — БД в РФ |
| [Object Storage](https://yandex.cloud/ru/docs/storage/) | S3 API | Bucket policy, presign | **P1** — private docs |
| [Managed K8s](https://yandex.cloud/ru/docs/managed-kubernetes/) | K8s API | Кластер приложений | P2 |
| [ALB](https://yandex.cloud/ru/docs/application-load-balancer/) | L7 | TLS, backends | P2 |
| [Container Registry](https://yandex.cloud/ru/docs/container-registry/) | Images | push/pull образов | P2 |

---

## Секреты, крипто, наблюдаемость

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Lockbox](https://yandex.cloud/ru/docs/lockbox/) | Secrets API | Версии секретов | **P1** |
| [KMS](https://yandex.cloud/ru/docs/kms/) | Crypto keys | Envelope encryption | **P1** |
| [Logging](https://yandex.cloud/ru/docs/logging/) | Logs API | Структурированные логи | P1 — без ПДн |
| [Monitoring](https://yandex.cloud/ru/docs/monitoring/) | Metrics | Алерты API/CPU | P1 |
| [Security conformity](https://yandex.cloud/ru/docs/security/conformity/) | 152-ФЗ / аттестации | Док для юриста/РКН | **P0** |

---

## SmartCaptcha (API)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [SmartCaptcha docs](https://yandex.cloud/ru/docs/smartcaptcha/) | Сервис | Клиентский виджет + server validate | **P1** |
| [Quickstart](https://yandex.cloud/ru/docs/smartcaptcha/quickstart) | Ключи | site key / server key | **P1** — заменить Google Enterprise |

---

## Vision / OCR (не LLM)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Vision](https://yandex.cloud/ru/docs/vision/) | CV hub | Модели зрения | **P1** — ТЗ-13 |
| [Concepts](https://yandex.cloud/ru/docs/vision/concepts/) | Модели | Возможности API | **P1** |
| [OCR text-detection](https://yandex.cloud/ru/docs/vision/operations/ocr/text-detection) | OCR | Текст со сканов | **P1** — `YANDEX_OCR_*` |
| [VisionOCR](https://yandex.cloud/ru/docs/visionocr/) | Отдельный OCR-сервис | Альтернативный вход | P1 — сверить актуальный продукт |

> LLM **не** использовать как основной OCR (ТЗ-06).

---

## Связь с AI Studio / Foundation Models

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [AI Studio service](https://yandex.cloud/ru/services/ai-studio) | Продукт | Вход в AI Studio | → `Yandex AI Studio/` |
| [foundation-models](https://yandex.cloud/ru/docs/foundation-models/) | Legacy docs hub | Старые URL FM → часто редирект в AI Studio | P1 |
| [FM API ref](https://yandex.cloud/ru/docs/foundation-models/api-ref/) | REST/gRPC | Низкоуровневый API моделей | P1 |
| [Search API](https://yandex.cloud/ru/docs/search-api/) | Search | Generative/web search | P2 |
| [ML tutorials](https://yandex.cloud/ru/docs/tutorials/ml-ai/) | Guides | IDE OpenAI-compatible | P1 |

---

## Карта усиления SFRFR

| Цель | Читать |
|------|--------|
| IAM + API key на folder | iam api-key · sa/create · resources-hierarchy |
| Self-hosted Supabase в РФ | compute · vpc · mpg · storage · lockbox |
| Private bucket сканов | storage bucket + IAM roles |
| SmartCaptcha на лид-форме | smartcaptcha quickstart + server verify |
| OCR ИЛС/трудовой | vision OCR ops |
| Аудит 152-ФЗ | security conformity · regions |

---

## Уже / рядом в проекте

| Тема | Где |
|------|-----|
| План локализации | `docs/specs/15-data-localization-ru.md` |
| AI + Vision политика | `docs/specs/06-integrations-and-security.md` |
| Env Cloud AI | `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `YANDEX_BASE_URL` |
| Workspace отдельно | ТЗ-14 — **не** эти ключи |
