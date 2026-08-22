# Финансы сотрудника: счета и оплаты

Вкладка «Финансы» — очередь счетов за информационно-документарную поддержку.
Формула «10% ЕДВ + 50% прибавки» в интерфейсе **не показывается**.

## Источник тарифов

`src/sfrfr/services/public_tariffs.py` = [тарифы сайта](https://proverkastaza.ru/tarify/) и `scripts/assets/yandex-business/price-list.yml`:

- диагностика 3 000 ₽;
- подготовка документов 5 000 ₽;
- сопровождение до подачи 8 000 ₽;
- перенос трудовой 100 ₽ / разворот.

Пакеты ЮKassa по-прежнему `DIAG` / `ACCOMP` / `SF_*`. `SF_*` в UI — «индивидуальное соглашение» (фиксированная сумма), без процентов.

## Миграция

`supabase/migrations/20260822190000_orders_finance_ops.sql`

Колонки `orders`: `invoice_number`, `due_at`, `invoice_status`, `pay_url`, `sent_channel`, `sent_at`, `cancel_reason`, `reminder_draft`, `service_label`, `next_action`.

Таблица `finance_audit` — только insert/select, без update/delete.

После деплоя кода:

```bash
# с VPS, через DATABASE_URL приложения
psql "$DATABASE_URL_LIBPQ" -v ON_ERROR_STOP=1 -f /opt/sfrfr/supabase/migrations/20260822190000_orders_finance_ops.sql
```

Или `bash scripts/vm_supabase_apply_migrations.sh` (нужен каталог `/tmp/sfrfr-migrations`).

Без миграции реестр всё равно строится из `orders.status` (`pending`/`paid`); сохранение ссылки, срока и аудита заработает после колонок.

## Роли

- operator — нет вкладки.
- expert — свои дела, ссылка и напоминание.
- admin — создать счёт, ручная оплата, отмена, тарифы.

## Rollout

1. Push в `main` → дождаться `deploy-vps`.
2. Применить SQL на self-host Postgres.
3. Проверить: нет текста про ЕДВ; KPI; скрыты тестовые; ЮKassa webhook по-прежнему ставит `paid`.

## Rollback

1. `git revert` коммита UI/API → `deploy-vps`.
2. Колонки можно оставить.
3. При необходимости:

```sql
drop table if exists public.finance_audit;
alter table public.orders
  drop column if exists invoice_number,
  drop column if exists due_at,
  drop column if exists invoice_status,
  drop column if exists pay_url,
  drop column if exists sent_channel,
  drop column if exists sent_at,
  drop column if exists cancel_reason,
  drop column if exists reminder_draft,
  drop column if exists service_label,
  drop column if exists next_action;
```
