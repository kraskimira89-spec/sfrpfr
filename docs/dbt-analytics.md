# dbt: обезличенная аналитика SFRFR

dbt не участвует в работе API и не хранит ПДн. Его роль ограничена схемами:

```text
public → analytics_source (обезличенные views) → analytics (витрины dbt)
```

`analytics_source` не содержит ФИО, телефонов, email, СНИЛС, документов, путей Storage, ID MAX, полных текстов/JSON сообщений, ID платёжного провайдера или точных денежных сумм. Суммы представлены диапазонами: `0`, `1–5 тыс.`, `5–10 тыс.`, `10+ тыс.`.

## Первичная настройка

1. Примените миграции Supabase (`analytics_source_and_role`, `grant_analytics_database_connect`, `analytics_marts_enable_rls`).
2. В SQL Editor Supabase установите уникальный пароль роли. Не добавляйте его в миграции или Git:

   ```sql
   alter role analytics_transformer password 'уникальный_длинный_секрет';
   ```

3. На VPS в `/opt/sfrfr/.env` укажите (значения как в локальном `.env` после настройки):

   ```env
   DBT_HOST=aws-<region>.pooler.supabase.com
   DBT_PORT=5432
   DBT_USER=analytics_transformer.<project-ref>
   DBT_PASSWORD=...
   DBT_DBNAME=postgres
   ```

   Используйте **direct connection** или **session pooler** PostgreSQL. Для session pooler имя роли имеет суффикс `.<project-ref>`. Transaction pooler не подходит для DDL dbt.
4. Скопируйте `analytics/profiles.yml.example` в `analytics/profiles.yml`. Файл игнорируется Git и читает только `DBT_*`.
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
dbt docs generate --profiles-dir . --no-populate-cache
```

На VPS есть обёртка:

```bash
SFRFR_ENV_FILE=/opt/sfrfr/.env /opt/sfrfr/scripts/dbt_run.sh
```

Запускайте её отдельным systemd timer или cron от пользователя `sfrfr`, например раз в сутки. Не добавляйте dbt в FastAPI startup или `scripts/vps_deploy.sh`.

### Замечания по VPS / pooler

- Direct host `db.<ref>.supabase.co` с VPS сейчас только IPv6 → `Network is unreachable`. Нужен IPv4 add-on или session pooler.
- Через session pooler `dbt build` на VPS часто зависает (relation cache / rename views / «idle in transaction» с ExclusiveLock). Локально с тем же pooler обычно стабильнее.
- Флаги в `dbt_run.sh`: `--threads 1 --no-populate-cache`.
- После серии оборванных прогонов убивайте сессии роли:  
  `select pg_terminate_backend(pid) from pg_stat_activity where usename = 'analytics_transformer' and pid <> pg_backend_pid();`
- Пока cron на VPS лучше не включать, пока нет direct IPv4; витрины можно пересобирать с ПК.

## Контроль доступа

Проверка от имени `analytics_transformer` должна позволять `select` из `analytics_source.*` и запрещать `public.clients`, `storage.objects` и `auth.users`. Роль не имеет `BYPASSRLS`, `CREATEDB`, `CREATEROLE` или доступа к API/Storage-ключам.

Витрины `analytics.*` (таблицы dbt):
- схема не в Data API (`config.toml` → `schemas`);
- `REVOKE` для `anon` / `authenticated`;
- **RLS включён без политик** — дополнительный барьер, если схема когда-либо попадёт в API;
- владелец `analytics_transformer` обходит RLS при `dbt build` (стандарт Postgres);
- post-hook в `dbt_project.yml` снова включает RLS после каждой сборки витрин.

## Синхронизация на VPS (когда SSH доступен)

```bash
# с ПК: скопировать код после merge/push, затем на сервере:
sudo -u sfrfr bash -lc 'cd /opt/sfrfr && . .venv/bin/activate && pip install -e ".[analytics]"'
# дописать DBT_* в /opt/sfrfr/.env (пароль не в git)
sudo -u sfrfr bash -lc 'cp /opt/sfrfr/analytics/profiles.yml.example /opt/sfrfr/analytics/profiles.yml'
# разовый прогон
SFRFR_ENV_FILE=/opt/sfrfr/.env /opt/sfrfr/scripts/dbt_run.sh
# cron (пример: 05:30 ежедневно)
# 30 5 * * * SFRFR_ENV_FILE=/opt/sfrfr/.env /opt/sfrfr/scripts/dbt_run.sh >> /var/log/sfrfr/dbt.log 2>&1
```
