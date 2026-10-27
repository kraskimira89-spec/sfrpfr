## Техническое задание для Яндекс Cloud AI-ассистента

### Цель

Сменить пароль роли Postgres self-host Supabase на VM C после раскрытия пароля в журнале агента. Обновить `POSTGRES_PASSWORD` / `DATABASE_URL` на app VM B так, чтобы API снова коннектился. Значение пароля **не печатать** в ответе и логах.

### Контекст

- Folder / cloud: см. `docs/ops/infrastructure-inventory.md` (VM C = self-host Supabase DNS `supabase.proverkastaza.ru`; VM B = app `proverkastaza.ru`).
- Секрет нового пароля владелец передаёт out-of-band (Lockbox version или файл на машине администратора `secrets/postgres-password-rotated.env`, ключ `POSTGRES_PASSWORD`). В это ТЗ пароль **не** вставлять.
- Документация стека: `docs/ops/supabase-selfhost-yandex-cloud.md`, `docs/ops/deploy-and-migrations.md`.

### Шаги

1. На VM C (SSH по ключу, user из inventory): найти compose `.env` с `POSTGRES_PASSWORD`.
2. Сделать backup копии `.env` с timestamp в `/root` или home (права 600).
3. Записать **новый** `POSTGRES_PASSWORD` в compose `.env` (значение взять из out-of-band канала владельца).
4. В контейнере `supabase-db` / `db` выполнить смену пароля роли `postgres` (и прочих ролей приложения, если они используют тот же секрет — сверить compose). Пример формы (пароль подставить из env, не echo):

```bash
docker compose exec -T db psql -U postgres -c "ALTER ROLE postgres WITH PASSWORD :'pw';"
```

Или `ALTER ROLE ... PASSWORD '…'` через переменную окружения без записи в shell history.

5. `docker compose up -d` (или recreate db + dependent services) так, чтобы PostgREST/GoTrue/Kong подхватили новый пароль.
6. На VM B: обновить `DATABASE_URL` в `/opt/sfrfr/.env` (или актуальный путь из `vps_deploy.sh`) — тот же новый пароль; `systemctl restart sfrfr-api` (и при необходимости ingest).
7. Проверка: `curl -fsS https://api.proverkastaza.ru/health` (или локальный health); `SELECT 1` из app через новый URL.
8. Старый пароль больше не должен принимать коннект.

### Ограничения

- Не публиковать пароль, connection string, JWT, service_role в ответе чата.
- Не трогать DNS, Lockbox catalog id без нужды (обновить payload Lockbox можно, если он SoT для `POSTGRES_PASSWORD`).
- Не делать `drop database` / destructive volume wipe.
- Не `terraform destroy`.

### Критерии готовности

- App health OK на новом пароле.
- Коннект со старым паролем — отказ auth.
- В ответе ассистента: только статусы шагов (ok/fail), **без** секретов.

---
Это техническое задание для выполнения Яндекс-ассистентом.
