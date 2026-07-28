# Yandex Cloud — пользовательская / консольная документация (оглавление)

Источники: [Документация](https://yandex.cloud/ru/docs/) · [Консоль](https://console.yandex.cloud/) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Связано: ТЗ-15 (локализация ПДн в РФ) · ТЗ-06 (AI/Vision) · SmartCaptcha вместо Google reCAPTCHA.

> **Не путать контуры:** Cloud (инфра + AI API-ключ/`folder_id`) ≠ Яндекс ID / Workspace OAuth (`proverkastaza@yandex.ru`, ТЗ-14).

---

## Как пользоваться

| Приоритет | Смысл |
|-----------|--------|
| **P0** | Нужно сейчас (биллинг, каталог, ключи, регионы РФ) |
| **P1** | План cutover: PG/Storage/Captcha/Compute в РФ |
| **P2** | Фоном (K8s, ALB, курсы) |

---

## Старт и консоль

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Обзор платформы](https://yandex.cloud/ru/docs/overview/) | Overview | Что такое YC, сервисы, SLA, 152-ФЗ | **P0** |
| [Как начать](https://yandex.cloud/ru/docs/overview/) → Начало работы | Onboarding | Регистрация, первый каталог | **P0** |
| [Консоль](https://console.yandex.cloud/) | Web UI | Управление облаком, каталогами, ключами | **P0** |
| [Регионы / гео](https://yandex.cloud/ru/docs/overview/concepts/regions) | Regions | Где ЦОД | **P0** — только РФ для ПДн |
| [Географический охват](https://yandex.cloud/ru/docs/overview/concepts/geo-scope) | Geo scope | Зоны доступности | **P1** |
| [Иерархия ресурсов](https://yandex.cloud/ru/docs/resource-manager/concepts/resources-hierarchy) | Cloud → Folder | Организация / облако / каталог | **P0** — `YANDEX_FOLDER_ID` |
| [Квоты и лимиты](https://yandex.cloud/ru/docs/overview/) → Квоты | Quotas | Ограничения сервисов | P1 |
| [Биллинг: аккаунт](https://yandex.cloud/ru/docs/billing/concepts/billing-account) | Billing | Платежный аккаунт | **P0** |
| [Активация пробного](https://yandex.cloud/ru/docs/billing/operations/activate-trial) | Trial | Старт без оплаты | P1 |

---

## IAM и доступ (консоль)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [IAM](https://yandex.cloud/ru/docs/iam/) | Identity | Пользователи, роли, SA | **P0** |
| [Аккаунты](https://yandex.cloud/ru/docs/iam/concepts/users/accounts) | Users / SA | Федеративные, сервисные | **P0** |
| [Сервисный аккаунт](https://yandex.cloud/ru/docs/iam/operations/sa/create) | Create SA | SA для API/VM | **P0** — Vision/Sheets SA уже есть паттерн |
| [API-ключ](https://yandex.cloud/ru/docs/iam/concepts/authorization/api-key) | API key | Статичный ключ к сервисам | **P0** — `YANDEX_API_KEY` |
| [Создать API-ключ](https://yandex.cloud/ru/docs/iam/operations/api-key/create) | Create key | Выпуск в консоли | **P0** |
| [IAM-токен](https://yandex.cloud/ru/docs/iam/concepts/authorization/iam-token) | IAM token | Короткоживущий | P1 — альтернатива ключу |
| [OAuth-токен (Cloud)](https://yandex.cloud/ru/docs/iam/concepts/authorization/oauth-token) | OAuth YC | Для CLI/пользователя | P2 — не Workspace OAuth |

---

## Инфра под ТЗ-15 (целевой РФ-контур)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Compute quickstart](https://yandex.cloud/ru/docs/compute/quickstart) | ВМ | Аренда VM | **P1** — self-hosted Supabase / API |
| [VPC](https://yandex.cloud/ru/docs/vpc/concepts/) | Сеть | VPC, подсети, SG | **P1** |
| [Managed PostgreSQL](https://yandex.cloud/ru/docs/managed-postgresql/quickstart) | MPG | Управляемый Postgres | **P1** — БД дел в РФ |
| [Object Storage / bucket](https://yandex.cloud/ru/docs/storage/concepts/bucket) | S3-совместимое | Приватные бакеты | **P1** — сканы вместо Supabase Cloud Storage |
| [Managed K8s](https://yandex.cloud/ru/docs/managed-kubernetes/quickstart) | MK8s | Оркестрация | P2 — если уйдём с одной VM |
| [ALB](https://yandex.cloud/ru/docs/application-load-balancer/) | Балансировщик | HTTPS вход | P2 |
| [Container Registry](https://yandex.cloud/ru/docs/container-registry/) | Образы | Docker registry | P2 |
| [Lockbox](https://yandex.cloud/ru/docs/lockbox/) | Секреты | Хранилище секретов | **P1** — вместо голого `.env` на диске |
| [KMS](https://yandex.cloud/ru/docs/kms/) | Ключи шифрования | Шифрование at rest | **P1** |
| [Logging](https://yandex.cloud/ru/docs/logging/) | Логи | Централизованные логи | P1 — без ПДн в логах |
| [Monitoring](https://yandex.cloud/ru/docs/monitoring/) | Метрики | Алерты | P1 |

---

## Безопасность и 152-ФЗ

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Security](https://yandex.cloud/ru/docs/security/) | Security hub | Обзор ИБ | **P1** |
| [Соответствие](https://yandex.cloud/ru/docs/security/conformity/) | Conformity | Стандарты / аттестации | **P0** — аргумент локализации |
| [Compliance](https://yandex.cloud/ru/docs/security/compliance/) | Compliance | Чеклисты | **P1** |
| [Туториалы security](https://yandex.cloud/ru/docs/tutorials/security/) | Tutorials | Практика hardening | P1 |

---

## SmartCaptcha (замена Google reCAPTCHA)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [SmartCaptcha](https://yandex.cloud/ru/docs/smartcaptcha/) | Сервис | Капча в РФ-контуре | **P1** — ТЗ-15 |
| [Quickstart](https://yandex.cloud/ru/docs/smartcaptcha/quickstart) | Старт | Ключи сайта/сервера | **P1** — форма лида на WP |

---

## CLI и смежные AI-сервисы (консоль/обзор)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [CLI quickstart](https://yandex.cloud/ru/docs/cli/quickstart) | yc CLI | Управление из терминала | **P1** |
| [Туториалы](https://yandex.cloud/ru/docs/tutorials/) | Tutorials | Пошаговые сценарии | P1 |
| [ML/AI tutorials](https://yandex.cloud/ru/docs/tutorials/ml-ai/) | ML guides | В т.ч. IDE + AI Studio | P1 |
| [Vision](https://yandex.cloud/ru/docs/vision/) | Computer Vision | OCR/детекция | **P1** — сканы ИЛС (ТЗ-13) |
| [Vision OCR op](https://yandex.cloud/ru/docs/vision/operations/ocr/text-detection) | Text detection | Распознавание текста | **P1** |
| [SpeechKit](https://yandex.cloud/ru/docs/speechkit/) | Speech | STT/TTS | P2 |
| [Translate](https://yandex.cloud/ru/docs/translate/) | Перевод | Translation API | P2 |
| [Search API](https://yandex.cloud/ru/docs/search-api/) | Поиск | Web/generative search | P2 |
| [AI Studio (продукт)](https://yandex.cloud/ru/services/ai-studio) | Маркетинг сервиса | Описание AI Studio | → папка `Yandex AI Studio/` |

---

## Быстрый указатель под SFRFR

| Задача | Смотреть |
|--------|----------|
| Выпустить `YANDEX_API_KEY` + folder | IAM API-ключ · иерархия ресурсов · консоль |
| План переноса БД/файлов в РФ | MPG · Object Storage · Compute · regions |
| Заменить reCAPTCHA | SmartCaptcha quickstart |
| OCR сканов | Vision OCR |
| Секреты / шифрование | Lockbox · KMS |
| Не смешать с почтой Яндекса | ТЗ-14 — отдельный OAuth, не Cloud API-ключ |
