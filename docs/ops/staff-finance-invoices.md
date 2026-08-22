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

## Автоматизация (без авторассылки клиенту)

- После принятия заказа (`contract_accepted`) создаётся **черновик счёта**: диагностика 3 000 ₽ или, если диагностика уже оплачена, подготовка документов 5 000 ₽.
- Ссылка в MAX / ЮKassa **не** создаётся сама — сотрудник нажимает «Ссылка» (копия) или «В MAX» (ссылка + QR).
- «Ссылка» создаёт **счёт ЮKassa** (`POST /v3/invoices`, доставка `self`): короткая ссылка вида `https://yookassa.ru/my/i/…`. Если счета в магазине нет — fallback на обычный `confirmation_url`.
- QR строится из этой ссылки (`GET /api/public/pay/{order_id}/qr.png`). SMS и email ЮKassa **не** используем: канал — MAX по кнопке сотрудника.
- После полной оплаты DIAG: `next_action` «Провести диагностику», этап `intake`/`new` → `documents_received`; если соглашение уже было — черновик счёта на подготовку документов (5 000 ₽).
- После полной оплаты ACCOMP: `next_action` «Готовить документы и проект обращения», pipeline не прыгает через OCR.
- Частичная оплата: задача сотруднику, этап не стартует.
- Чек от клиента: OCR + сверка ИНН/счёта ООО «ПОД ПРИСМОТРОМ» или ЮKassa и суммы. Совпало — как успешная оплата, следующий этап. Если webhook ЮKassa уже пришёл — чек не просим. Канон: `src/sfrfr/services/payment_receipt.py`.
- Каждое утро (07:00 МСК) `sfrfr finance-due-tick`:
  - за 24 часа до срока — задача «Проверить оплату»;
  - 1–3 дня после срока — черновик вежливого напоминания (без отправки).

Включить таймер на VPS:

```bash
sudo cp /opt/sfrfr/docs/systemd/sfrfr-finance-due.service /etc/systemd/system/
sudo cp /opt/sfrfr/docs/systemd/sfrfr-finance-due.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sfrfr-finance-due.timer
```

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
