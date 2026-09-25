# Drain Supabase Cloud после cutover на YC

После стабильности прод-контура на `https://supabase.proverkastaza.ru` (рекомендуется **24–72 ч** мониторинга Auth/API).

**Не удалять Cloud в день cutover** — нужен rollback.

## Критерии готовности к drain

- [ ] API `/health` = 200, `supabase_configured=true`
- [ ] Cabinet + admin открываются, magic link / OTP работает
- [ ] Лиды / кейсы пишутся в YC (row counts растут только там)
- [ ] `DATABASE_URL` / `DBT_*` на VPS → YC Postgres **`:5433`** (не `*.supabase.co`, не Supavisor `:5432`)
- [ ] Nightly `sfrfr-dbt.timer` (если включён) успешен против YC (`journalctl -u sfrfr-dbt.service`)
- [ ] В `.env`: `DBT_PORT=5433`, `DBT_SSLMODE=disable` (defaults в `dbt_run.sh` / `profiles.yml.example` — тоже 5433/disable)
- [ ] Нет критичных ошибок Auth/Storage в логах 24–72 ч
- [ ] Бэкап YC Postgres + `restore_drill` свежий

## Шаги drain (когда критерии ✅)

1. **Freeze Cloud** — в Dashboard: pause project / отключить API keys usage (или revoke anon/service в Cloud UI).
2. **Экспорт подтверждения** — сохранить скрин/PDF статуса проекта и дату pause.
3. **Запрос удаления данных** — [Supabase support](https://supabase.com/dashboard/support/new): удаление проекта `frualvycousvvyjivybu` и подтверждение уничтожения копий (152-ФЗ).
4. **Локальные хвосты** — убрать Cloud URL из `.env` / secrets зеркал; оставить только в `secrets/` как архив rollback до подтверждения удаления.
5. **Документы** — акт/письмо в `docs/ops/` или юр. архив оператора; обновить политику ПДн § трансграничка.
6. **DNS/ключи** — убедиться, что нигде в проде нет `frualvycousvvyjivybu.supabase.co`.

## Rollback (пока Cloud жив)

1. Вернуть на VPS `SUPABASE_URL` / keys / cabinet `NEXT_PUBLIC_*` на Cloud.
2. `DATABASE_URL` / `DBT_*` → Cloud direct/pooler.
3. `systemctl restart sfrfr-api sfrfr-cabinet sfrfr-admin`
4. Auth redirects в Cloud Dashboard (см. legacy-блок в [supabase-auth-redirects.md](./supabase-auth-redirects.md)).

## Supabase MCP в Cursor смотрит в Cloud, не в прод

MCP-сервер `mcp.supabase.com` видит только Cloud-проект `frualvycousvvyjivybu` (legacy, rollback).
Его таблицы, миграции и advisors **не отражают прод**: не применять туда миграции,
не создавать `create_branch`, не делать выводов о проде по MCP-аудиту.

Сверка прода (self-host YC) — read-only скрипт, `DATABASE_URL` из `secrets/`:

```powershell
.\.venv\Scripts\python.exe scripts/verify_prod_schema_drift.py
```

Скрипт проверяет объекты 15 миграций (`20260727…`–`20260924…`) и security-сигналы
(SECURITY DEFINER в `public`, `rls_auto_enable`, RLS без политик, `auth.uid()` в
`marketing_consents_select_own`). Выводит только имена объектов, без данных и DSN.

## Связанное

- [15-data-localization-ru.md](../specs/15-data-localization-ru.md) — фаза 2 шаг 7
- [supabase-selfhost-yandex-cloud.md](./supabase-selfhost-yandex-cloud.md)
- Скрипт переключения PG: `scripts/vps_switch_db_to_yc.sh`
