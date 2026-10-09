# ТЗ-15: локализация ПДн и миграция в российский контур

## Цель

Обеспечить соответствие части 5 статьи 18 и статьи 12 № 152-ФЗ: запись, хранение и извлечение ПДн граждан РФ — в базах на территории РФ; трансграничная передача — только после уведомления РКН и при минимально необходимом составе данных.

## Текущий контур (после cutover 2026-08-03)

| Слой | Факт |
|---|---|
| БД / Auth / Storage | **Self-hosted Supabase** в **Yandex Cloud** (РФ), канон: [supabase-selfhost-yandex-cloud.md](../ops/supabase-selfhost-yandex-cloud.md) |
| Файлы | Storage self-hosted + Object Storage YC для бэкапов |
| Captcha | **Yandex SmartCaptcha** |
| Резервные копии | только ЦОД в РФ + проверка восстановления |

**Не считать прокси/Франкфурт/согласие клиента заменой локализации.**

## Целевая архитектура (оптимальный вариант)

```text
Yandex Cloud (РФ)
├── Compute / Managed K8s / VM  → self-hosted Supabase (Auth, API, Realtime)
├── Managed PostgreSQL (или PG в составе Supabase) → данные кейсов, RLS
├── Object Storage              → private bucket документов
├── Backups                     → только регионы РФ
└── Yandex SmartCaptcha         → защита публичных форм

FastAPI (VPS/YC) ↔ тот же клиентский SDK Supabase (смена URL/ключей)
WordPress / кабинеты / MAX — без смены контрактов API
```

Альтернативы ЦОД: Selectel или иной подтверждённый российский провайдер — допустимы при тех же требованиях (сервер + бэкапы в РФ).

## Рекомендации (обязательные к учёту)

1. **Перенести контур данных в РФ**: self-hosted Supabase; сервер и резервные копии только в РФ; PostgreSQL, Auth и Storage — там же.
2. **Заменить Google reCAPTCHA на Yandex SmartCaptcha** (у Google нет российского региона; сетевой адрес и сведения о браузере могут уходить за рубеж).
3. **Не использовать иностранный hosted-контур** как прод-базу ПДн: российских регионов у hosted Supabase нет.
4. После миграции:
   - актуализировать уведомление оператора;
   - обновить политику и согласие;
   - не держать рабочие URL/ключи зарубежного контура в проекте;
   - проверить восстановление российских резервных копий.

## Supabase vs Yandex Cloud (не взаимозаменяемые продукты)

| | **Supabase** | **Yandex Cloud** |
|---|---|---|
| Что это | Платформа приложения: Postgres + Auth + Storage + RLS + Realtime + REST/JS SDK | Облачная инфраструктура (IaaS/PaaS) в РФ: ВМ, Managed PG, Object Storage, сеть, IAM |
| Роль в SFRFR | Слой данных и входа клиентов/сотрудников | Место размещения (ЦОД РФ) и облачные сервисы |
| Cloud-версия | Хостинг за рубежом (нет региона РФ) | Регионы РФ (подтверждённая локализация) |
| Self-host | Можно развернуть на любом облаке/VPS | Не «заменяет» Auth/RLS из коробки — даёт PG + S3 + ВМ |
| Аналог SmartCaptcha | нет | Yandex SmartCaptcha |
| Для проекта | **Продукт**, с которым работает код | **Площадка**, куда переносим self-hosted Supabase |

Итог: миграция — не «выключить Supabase и включить Yandex Cloud», а **разместить тот же стек Supabase (или эквивалент PG+Auth+Storage) внутри Yandex Cloud**.

Вариант «только Managed PostgreSQL + Object Storage YC без Supabase» возможен, но дороже по разработке (своя Auth, signed URL, RLS-эквивалент) — не целевой для SFRFR.

## План миграции

### Фаза 0. MVP (историческая) — до cutover

- Env-абстракция: URL/ключи только из env (`SUPABASE_URL`, keys).
- ТЗ-15 принято; риски зафиксированы в политике ПДн.

Критерий выхода: выполнен; далее — фазы 1–2.

### Фаза 1. Подготовка РФ-контура (после MVP / при готовности)

1. Аккаунт Yandex Cloud, каталог, бюджет, VPC в регионе РФ. ✅ staging folder + Terraform.
2. Развернуть self-hosted Supabase (Docker) на ВМ. ✅ `51.250.13.240`, Compose healthy.
3. Object Storage: private bucket staging. ✅ `sfrfr-staging-backup-*` (бэкапы).
4. Сеть: TLS, firewall; Studio не публично. ✅ SG + Caddy HTTPS (`supabase.proverkastaza.ru`, LE 2026-08-03).
5. Бэкапы PG только РФ + restore-drill. ✅ скрипты прогнаны на ВМ (2026-08-02).
6. Staging-схема + синтетика. ✅ миграции + SYNTH seed.
7. RLS/интеграционные тесты против staging URL — частично (HTTPS smoke 2026-08-03); расширить по мере подключения app env.
8. Пилот SmartCaptcha. ✅ ключи YC `proverkastaza`, `CAPTCHA_PROVIDER=yandex`, MU на витрине ([yandex-smartcaptcha-staging.md](../ops/yandex-smartcaptcha-staging.md)).

Критерий выхода: staging в РФ зелёный; restore бэкапа подтверждён; SmartCaptcha на staging/витрине ок.

### Фаза 2. Cutover данных

1. Freeze записей / короткое окно обслуживания (или dual-write на период).
2. Экспорт: `pg_dump` / логический dump + объекты Storage.
3. Импорт в РФ; сверка checksum/row counts по ключевым таблицам (`clients`, `cases`, `documents`, auth users).
4. Переключить FastAPI/кабинеты на новые `SUPABASE_URL` / keys.
5. Обновить Auth redirect URLs, CORS, webhook’и.
6. Мониторинг ошибок Auth/Storage 24–72 ч.
7. Прод только РФ-контур; зарубежный hosted-контур выведен из конфигурации проекта.

**Факт 2026-08-03:** cutover выполнен — VPS API/cabinet/admin → `https://supabase.proverkastaza.ru`; импорт `clients=11`, `cases=9`, `auth.users=10`. Пароли Auth не переносились (Admin API) — вход через magic link/OTP. `DATABASE_URL`/`DBT_*` → YC Postgres через SG allowlist.

**Факт 2026-10-09:** в репозитории и env-шаблонах оставлена только self-host БД (канон: [supabase-selfhost-yandex-cloud.md](../ops/supabase-selfhost-yandex-cloud.md)).

Критерий выхода: прод читает/пишет только РФ.

### Фаза 3. Captcha и документы 152-ФЗ

1. [x] Заменить Google reCAPTCHA → Yandex SmartCaptcha в WP и API.
2. [x] Запретить Google captcha и прямые иностранные LLM в production-коде.
3. [x] Обновить Политику, Согласие и Правила файлов браузера (редакции 2026-08-03).
4. [x] Отключить runtime-выгрузку Google Sheets; управленческий контур — dbt/DataLens.
5. [x] Конфигурация проекта указывает только на self-host YC (2026-10-09).

Критерий выхода: в prod нет Google captcha; документы соответствуют фактическому контуру.

### Фаза 4. Закрепление

- Регламент бэкапов и квартальный restore-drill.
- Runbook: подъём Supabase на YC, ротация ключей, инцидент утечки.
- Актуализация ТЗ-01 / ТЗ-06 (таблица технологий → self-hosted + YC).

## Вне скоупа этой миграции

- Смена WordPress-хостинга (если уже в РФ — ок).
- Отказ от Yandex AI Studio / Vision (уже РФ).
- Полный отказ от amoCRM/MAX/ЮKassa (российские операторы по своим документам).
- Переписывание бизнес-логики FastAPI.

## Риски и митигация

| Риск | Митигация |
|---|---|
| Downtime cutover | staging-репетиция; dual-write или maintenance window |
| Расхождение Auth users | миграция `auth.users` + проверка magic link / сессий |
| Утечка service role | ключи только на сервере; ротация после cutover |
| Стоимость self-host | мониторинг CPU/диска; Managed PG при росте |
| Задержка юр. уведомления РКН | не расширять иностранный контур до выполнения ст. 12 |

## Связанные документы

- [01-architecture.md](01-architecture.md)
- [06-integrations-and-security.md](06-integrations-and-security.md)
- [07-mvp-roadmap.md](07-mvp-roadmap.md)
- [../contracts/pdn-policy.md](../contracts/pdn-policy.md)
- [../ops/supabase-selfhost-yandex-cloud.md](../ops/supabase-selfhost-yandex-cloud.md) — пошаговый runbook: Docker Compose на ВМ YC
- Canvas (схема/сравнение): открыть рядом с чатом `data-localization-options.canvas.tsx`

## Критерии приёмки ТЗ (документальные)

- [x] Целевой вариант зафиксирован: self-hosted Supabase в Yandex Cloud + РФ Storage + SmartCaptcha.
- [x] Исторический MVP-контур закрыт cutover’ом; в проекте только self-host YC.
- [x] План миграции по фазам 0–4 описан.
- [x] Разница Supabase vs Yandex Cloud зафиксирована в таблице.
- [x] Фаза 1 — РФ-инфраструктура, DNS/TLS, миграции, restore-drill и SmartCaptcha готовы.
- [x] Фаза 2 — production переключён на self-hosted Supabase в Yandex Cloud.
- [x] Фаза 3 — Google captcha/Sheets отключены в runtime, документы обновлены.
- [x] Фаза 4 — в проекте остаётся только канон self-host YC (2026-10-09).
