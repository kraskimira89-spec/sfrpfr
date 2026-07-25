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
   DBT_HOST=db.<project-ref>.supabase.co
   DBT_PORT=5432
   DBT_USER=analytics_transformer
   DBT_PASSWORD=...
   DBT_DBNAME=postgres
   ```

   Для стабильных DDL dbt используйте **direct PostgreSQL connection**. Для IPv4-only VPS
   включите [Supabase IPv4 add-on](https://supabase.com/docs/guides/platform/ipv4-address);
   session/transaction pooler не используются.
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
dbt docs generate --profiles-dir . --threads 1 --no-populate-cache
```

На VPS есть обёртка для ручного запуска:

```bash
SFRFR_ENV_FILE=/opt/sfrfr/.env /opt/sfrfr/scripts/dbt_run.sh
```

Не добавляйте dbt в FastAPI startup или `scripts/vps_deploy.sh`.

### Nightly systemd timer на VPS

После включения IPv4 add-on и обновления `DBT_*` в `/opt/sfrfr/.env`:

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
перезагрузки VPS и ограничивает выполнение 45 минут. dbt работает последовательно
(`--threads 1 --no-populate-cache`), а логи остаются в `journald` на VPS.

### Требование подключения

До включения IPv4 add-on direct host `db.<project-ref>.supabase.co` на VPS недоступен:
у него только IPv6, а сеть VPS IPv6 не маршрутизирует. Не используйте session pooler
для dbt DDL: ранее он оставлял транзакции с блокировками и приводил к зависанию сборки.

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
