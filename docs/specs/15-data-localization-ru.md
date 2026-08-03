# ТЗ-15: локализация ПДн и миграция в российский контур

## Цель

Обеспечить соответствие части 5 статьи 18 и статьи 12 № 152-ФЗ: запись, хранение и извлечение ПДн граждан РФ — в базах на территории РФ; трансграничная передача — только после уведомления РКН и при минимально необходимом составе данных.

## Решение на MVP (зафиксировано)

| Слой | На MVP | После MVP (целевой контур) |
|---|---|---|
| БД / Auth / Storage | **Supabase Cloud** (как сейчас) | Self-hosted Supabase в **Yandex Cloud** (РФ) |
| Файлы | Supabase Storage | Object Storage Yandex Cloud (или Storage self-hosted Supabase на дисках в РФ) |
| Captcha | Google reCAPTCHA Enterprise | **Yandex SmartCaptcha** |
| Резервные копии | по политике Supabase Cloud | только ЦОД в РФ + проверка восстановления |

MVP сознательно оставляет Supabase Cloud: быстрее запуск, без смены Auth/RLS/миграций. Риск 152-ФЗ на MVP компенсируется документированием (политика ПДн §11), уведомлением РКН при необходимости и планом cutover ниже. **Не считать прокси/Франкфурт/согласие клиента заменой локализации.**

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
3. **Не использовать Supabase Cloud как основную прод-базу ПДн** после MVP: российских регионов нет.
4. Если иностранный сервис временно остаётся (текущий MVP):
   - сначала писать в российскую БД (после появления РФ-контура) либо до cutover — минимизировать состав и сроки;
   - передавать только минимальный состав;
   - до трансграничной передачи — уведомление РКН по ст. 12 № 152-ФЗ;
   - поручение обработки и оценка рисков;
   - страна, получатель, цели и состав — в политике/согласии.
5. После миграции:
   - актуализировать уведомление оператора;
   - обновить политику и согласие;
   - удалить зарубежные копии и получить подтверждение удаления;
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

### Фаза 0. MVP (сейчас) — без смены БД

- Оставить Supabase Cloud.
- Зафиксировать в политике ПДн трансграничный риск (уже есть §11).
- Юридический трек параллельно: уведомление РКН / поручение / оценка рисков — по решению оператора.
- Подготовить env-абстракцию: все URL/ключи только из env (`SUPABASE_URL`, keys) — без хардкода региона.
- **Не** начинать dual-write на MVP без отдельного решения.

Критерий выхода: продукт на MVP работает; ТЗ-15 принято; риски осознаны.

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
7. При стабильности — drain старого Cloud; запросить удаление данных у Supabase Inc. и сохранить подтверждение.

**Факт 2026-08-03:** cutover выполнен — VPS API/cabinet/admin → `https://supabase.proverkastaza.ru`; импорт `clients=11`, `cases=9`, `auth.users=10`. Cloud проект ещё не удалён (шаг 7). Пароли Auth не переносились (Admin API) — вход через magic link/OTP.

Критерий выхода: прод читает/пишет только РФ; зарубежный контур пуст или уничтожен с актом.

### Фаза 3. Captcha и документы 152-ФЗ

1. Заменить Google reCAPTCHA → Yandex SmartCaptcha в WP + `integrations/recaptcha` (или новый модуль).
2. Убрать GCP-зависимости captcha из prod env.
3. Обновить `docs/contracts/pdn-policy.md`, согласие, уведомление оператора.
4. В политике: страна/получатель/цели только для оставшихся иностранных сервисов (если есть).

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
- [x] На MVP разрешён временный Supabase Cloud.
- [x] План миграции по фазам 0–4 описан.
- [x] Разница Supabase vs Yandex Cloud зафиксирована в таблице.
- [ ] Фаза 1 — в работе (инфра staging есть; DNS/TLS, миграции, restore-drill, SmartCaptcha-ключи — хвосты).
- [ ] Фазы 2–4 — после MVP / после зелёной фазы 1.
