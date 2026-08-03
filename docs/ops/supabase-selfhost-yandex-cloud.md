# Self-hosted Supabase в Yandex Cloud (ТЗ-15)

Практический runbook: тот же стек Supabase (Auth + Postgres + Storage + RLS + API), но на ВМ в регионе РФ.

Официальная база: [Self-Hosting with Docker](https://supabase.com/docs/guides/self-hosting/docker)  
Состав сервисов: [supabase/docker](https://github.com/supabase/supabase/tree/master/docker)

На MVP прод остаётся на Supabase Cloud. Этот документ — для **staging → cutover** после MVP.

## Что получится

```text
Internet
   │ HTTPS (443)
   ▼
ALB / Nginx / Caddy  (TLS, только нужные пути)
   │
   ▼
Compute Cloud VM (регион РФ)  — Docker Compose:
   Kong/Envoy → Auth (GoTrue), PostgREST, Realtime, Storage, Studio*
   Postgres (+ расширения Supabase) на томе ВМ
   (опц.) файлы → Object Storage YC (S3)

FastAPI / cabinet / admin
   SUPABASE_URL=https://supabase.ваш-домен.ru
   SUPABASE_ANON_KEY / SERVICE_ROLE_KEY  (из .env стека)
```

\* Studio — только через VPN/bastion, не в публичный интернет.

## Вариант A (рекомендуемый старт) — одна ВМ + Docker Compose

Минимум движущихся частей: весь стек как у официального self-host. Подходит для staging и первого прод-cutover.

### 1. Инфра в Yandex Cloud

1. Каталог + биллинг; регион **РФ** (например `ru-central1`).
2. **VPC** + подсеть; Security Group:
   - inbound: `443` с интернета (или только с IP VPS FastAPI / ALB);
   - `22` только с bastion/вашего IP;
   - Postgres `5432` **не** открывать в интернет.
3. **Compute VM**:
   - Ubuntu 22.04/24.04;
   - от **4 vCPU / 8 GB RAM** (лучше 8/16 для комфорта);
   - диск ≥ 100 GB SSD (данные PG + объекты Storage).
4. Статический публичный IP (или внутренний IP + ALB).
5. DNS: `supabase.proverkastaza.ru` → IP/ALB.
6. (Желательно) **Lockbox** для секретов; **KMS** для диска.

### 2. ПО на ВМ

```bash
# Docker Engine + Compose plugin (официальный install Docker)
sudo apt update && sudo apt install -y git curl
# … установить Docker по docs.docker.com …

git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker
cp .env.example .env
```

Либо quick start с [доки Supabase](https://supabase.com/docs/guides/self-hosting/docker#quick-start-linux) (`run.sh`), если дистрибутив поддерживается.

### 3. Секреты и URL (обязательно до первого `up`)

В `.env` сгенерировать **свои** значения (дефолты из example — нельзя в прод):

| Переменная | Назначение |
|---|---|
| `POSTGRES_PASSWORD` | пароль БД |
| `JWT_SECRET` | ≥ 32 символа; им подписаны anon/service keys |
| `ANON_KEY` / `SERVICE_ROLE_KEY` | JWT по гайду Supabase (или скрипт из доки) |
| `SITE_URL` | URL кабинета (`https://cabinet.proverkastaza.ru`) |
| `API_EXTERNAL_URL` | публичный URL API стека (`https://supabase.…`) |
| `SUPABASE_PUBLIC_URL` | то же для Studio/ссылок |

Дополнительно для SFRFR:

- Auth redirect URLs — как в [supabase-auth-redirects.md](supabase-auth-redirects.md), но на новый хост.
- SMTP для magic link / OTP — свой (Яндекс Workspace / иной РФ), не облачный default.

Генерация ключей: раздел *Configuring and securing* в [официальном гайде](https://supabase.com/docs/guides/self-hosting/docker).

### 4. Запуск

```bash
docker compose pull
docker compose up -d
docker compose ps   # все healthy
```

Проверка:

```bash
curl -sS "$API_EXTERNAL_URL/rest/v1/" -H "apikey: $ANON_KEY" | head
```

Studio: `http://localhost:8000` через SSH-туннель, не публиковать.

### 5. TLS снаружи

Варианты:

- **Caddy/Nginx** override из репозитория Supabase (`docker-compose.caddy.yml` / nginx), Let's Encrypt; или
- **Application Load Balancer** YC + сертификат Certificate Manager → backend `:8000` на ВМ.

Наружу только HTTPS. HTTP → redirect.

### 6. Миграции схемы SFRFR

На staging указать CLI/CI на новый проект:

```bash
# пример: remote с self-host (после настройки db connection string)
supabase db push   # или прогнать файлы из supabase/migrations/
```

Либо `psql` на контейнер `db` / порт только с localhost.  
Прогнать интеграционные RLS-тесты против нового `SUPABASE_URL`.

### 7. Подключение приложения (без смены кода)

На FastAPI / cabinet / admin (staging env):

```env
SUPABASE_URL=https://supabase.proverkastaza.ru
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
NEXT_PUBLIC_SUPABASE_URL=https://supabase.proverkastaza.ru
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

Клиентский SDK тот же. Cutover = смена env + рестарт сервисов.

### 8. Бэкапы (только РФ)

- Снапшоты диска ВМ по расписанию (YC).
- Логический dump:

```bash
docker compose exec -T db pg_dump -U postgres > backup-$(date +%F).sql
```

- Копии dump → Object Storage бакет в `ru-central1`, без реплик за рубеж.
- Раз в квартал: restore на чистую ВМ (критерий фазы 1 ТЗ-15).

---

## Вариант B (позже) — Managed PostgreSQL + Object Storage

Когда вырастет нагрузка / нужна управляемая БД:

1. **Managed PostgreSQL** в РФ — перенести данные; в Compose отключить встроенный `db`, указать external DSN (нужны расширения, которые ждёт Supabase — сверять с докой self-host).
2. **Object Storage** — S3-совместимый endpoint для сервиса Storage (ключи IAM, private bucket).
3. Auth/PostgREST/Realtime/Storage API остаются в Compose на ВМ или переезжают в Managed K8s.

Сложнее в настройке расширений и совместимости — **не стартовать с B**, пока A не отработан на staging.

---

## Cutover с Cloud → YC (кратко)

1. Freeze / короткое окно.
2. `pg_dump` + выгрузка Storage с Cloud.
3. Импорт в self-host; сверка счётчиков (`clients`, `cases`, `documents`, `auth.users`).
4. Переключить env на VPS; обновить Auth redirects / CORS.
5. Мониторинг 24–72 ч.
6. Запросить удаление данных у Supabase Inc.; сохранить подтверждение.
7. Обновить политику ПДн (ТЗ-15, фаза 3).

Детали фаз: [../specs/15-data-localization-ru.md](../specs/15-data-localization-ru.md).

---

## Операционные скрипты (репо)

| Скрипт | Назначение |
|--------|------------|
| `scripts/vm_supabase_enable_caddy.sh` | TLS: Caddy + `PROXY_DOMAIN=supabase.proverkastaza.ru` |
| `scripts/vm_supabase_apply_migrations.sh` | `supabase/migrations` + синтетический seed |
| `scripts/staging_seed_synthetic.sql` | SYNTH-клиенты/кейсы (не ПДн) |
| `scripts/vm_supabase_backup.sh` | `pg_dump -Fc` → `/data/backups/…` (РФ-диск ВМ) |
| `scripts/vm_supabase_restore_drill.sh` | restore в БД `restore_drill` |
| `docs/ops/yandex-smartcaptcha-staging.md` | пилот SmartCaptcha |

## Чеклист приёмки staging

- [x] ВМ в регионе РФ (`ru-central1`), Compose healthy (2026-08-02)
- [x] Секреты из Lockbox (не дефолтные JWT); Studio не на `:8000` с интернета (SG)
- [x] HTTPS на `API_EXTERNAL_URL` — DNS A + Let's Encrypt OK (2026-08-03), `https://supabase.proverkastaza.ru`
- [x] Миграции SFRFR (11) + SYNTH seed применены (2026-08-02)
- [x] Magic link / OTP: Auth Send Email Hook на staging → `api.proverkastaza.ru` → Яндекс SMTP (см. `vm_supabase_enable_auth_email_hook.sh`)
- [x] Restore-drill: dump + `restore_drill` с `public_tables=16` (ACL warnings ок)
- [x] SmartCaptcha: ключи YC + `CAPTCHA_PROVIDER=yandex` на API/VPS; MU-плагин на витрине (`wp_apply_landing_vps.sh`)
- [ ] Cabinet/admin/API на staging URL только через env (не prod cutover)

## Чего не делать

- Не открывать Postgres в интернет.
- Не считать «прокси перед Cloud» локализацией.
- Не класть `SERVICE_ROLE_KEY` в браузер / WordPress.
- Не начинать прод-cutover без репетиции на staging.
