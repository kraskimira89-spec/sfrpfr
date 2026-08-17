# dbt: обезличенная аналитика SFRFR

dbt не участвует в работе API и не хранит ПДн. Его роль ограничена схемами:

```text
public → analytics_source (обезличенные views) → analytics (витрины dbt) → DataLens
```

`analytics_source` не содержит ФИО, телефонов, email, СНИЛС, документов, путей Storage, ID MAX, полных текстов/JSON сообщений, ID платёжного провайдера или точных денежных сумм. Суммы представлены диапазонами: `0`, `1–5 тыс.`, `5–10 тыс.`, `10+ тыс.`.

## Первичная настройка (канон: YC self-host)

1. Примените миграции на self-host Postgres (`analytics_source_and_role`,
   `grant_analytics_database_connect`, `analytics_marts_enable_rls`) —
   см. `scripts/vm_supabase_apply_migrations.sh` / `supabase/migrations/`.
2. Установите уникальный пароль роли (не в миграциях и не в Git):

   ```sql
   alter role analytics_transformer password 'уникальный_длинный_секрет';
   ```

3. На VPS в `/opt/sfrfr/.env` укажите:

   ```env
   DBT_HOST=51.250.13.240
   DBT_PORT=5433
   DBT_USER=analytics_transformer
   DBT_PASSWORD=...
   DBT_DBNAME=postgres
   DBT_SSLMODE=disable
   ```

   На YC: `:5432` = Supavisor (не для dbt DDL); **прямой Postgres** — `:5433`
   (`docker-compose.sfrfr-direct-pg.yml`). SG: `allowed_postgres_cidrs`.
   Переключение с Cloud: `scripts/vps_switch_db_to_yc.sh`.

   Если `DBT_PORT` / `DBT_SSLMODE` не заданы, обёртки и `profiles.yml.example`
   по умолчанию используют **`5433`** и **`disable`**.
4. Скопируйте `analytics/profiles.yml.example` в `analytics/profiles.yml`.
   Файл игнорируется Git и читает только `DBT_*`.
5. Установите зависимости на машине запуска:

   ```bash
   pip install -e '.[analytics]'
   ```

## Проверка и запуск

```bash
cd analytics
dbt debug --profiles-dir .
dbt parse --profiles-dir .
dbt build --profiles-dir . --threads 1 --no-populate-cache
# RLS/REVOKE — только через обёртку (не голый dbt build):
#   scripts/dbt_apply_rls.sh
dbt docs generate --profiles-dir . --threads 1 --no-populate-cache
```

На VPS есть обёртка для ручного запуска (build + RLS + docs):

```bash
SFRFR_ENV_FILE=/opt/sfrfr/.env /opt/sfrfr/scripts/dbt_run.sh
```

Не добавляйте dbt в FastAPI startup или `scripts/vps_deploy.sh`.

### Nightly systemd timer на VPS

После cutover `DBT_*` на YC `:5433`:

```bash
sudo cp /opt/sfrfr/docs/systemd/sfrfr-dbt.service /etc/systemd/system/
sudo cp /opt/sfrfr/docs/systemd/sfrfr-dbt.timer /etc/systemd/system/
sudo -u sfrfr cp /opt/sfrfr/analytics/profiles.yml.example /opt/sfrfr/analytics/profiles.yml
sudo systemctl daemon-reload
sudo systemctl enable --now sfrfr-dbt.timer
sudo systemctl start sfrfr-dbt.service
systemctl list-timers sfrfr-dbt.timer
journalctl -u sfrfr-dbt.service -n 100 --no-pager
```

Timer запускает dbt ежедневно в 05:30 по Москве, сохраняет пропущенный запуск после
перезагрузки VPS и ограничивает работу 45 минут. dbt работает последовательно
(`--threads 1 --no-populate-cache`); RLS/REVOKE для витрин применяются
отдельным `scripts/dbt_apply_rls.sh` после build. Логи — в `journald` на VPS.

`ConditionPathExists=/opt/sfrfr/analytics/profiles.yml` — без этого файла unit
не стартует.

### Требование подключения

Для dbt на YC используйте **только прямой Postgres `:5433`**. Не используйте
Supavisor (`:5432`) для DDL: ранее session pooler оставлял транзакции с
блокировками и приводил к зависанию сборки.

## Контроль доступа

Проверка от имени `analytics_transformer` должна позволять `select` из
`analytics_source.*` и запрещать `public.clients`, `storage.objects` и
`auth.users`. Роль не имеет `BYPASSRLS`, `CREATEDB`, `CREATEROLE` или доступа
к API/Storage-ключам.

Витрины `analytics.*` (таблицы dbt):

- схема не в Data API (`config.toml` → `schemas`);
- `REVOKE` для `anon` / `authenticated` через `scripts/dbt_apply_rls.sh`;
- **RLS включён без политик** — дополнительный барьер, если схема когда-либо
  попадёт в API;
- владелец `analytics_transformer` обходит RLS при `dbt build` (стандарт Postgres);
- post-hook внутри dbt **не** используется (зависания на COMMIT); только
  `dbt_apply_rls.sh` после build в `dbt_run.sh`.

## Синхронизация на VPS (когда SSH доступен)

```bash
# с ПК: скопировать код после merge/push, затем на сервере:
sudo -u sfrfr bash -lc 'cd /opt/sfrfr && . .venv/bin/activate && pip install -e ".[analytics]"'
# дописать DBT_* в /opt/sfrfr/.env (пароль не в git); порт 5433
sudo -u sfrfr bash -lc 'cp /opt/sfrfr/analytics/profiles.yml.example /opt/sfrfr/analytics/profiles.yml'
# разовый прогон
SFRFR_ENV_FILE=/opt/sfrfr/.env /opt/sfrfr/scripts/dbt_run.sh
```

## Legacy: Supabase Cloud (только rollback / drain)

До полного drain Cloud rollback может временно вернуть:

```env
# DBT_HOST=db.<project-ref>.supabase.co
# DBT_PORT=5432
# DBT_SSLMODE=require
```

Не смешивать с прод-YC. Чеклист: `docs/ops/supabase-cloud-drain-checklist.md`.
