# Архитектура B2C: данные, RLS, модули

**Версия:** 0.1  
**Дата:** 2026-07-22  
**Стек:** FastAPI + Supabase/Postgres + CRM Taganay + Google Sheets (обезличенно)

## 1. Модули кода (целевая структура)

```text
src/sfrfr/
├── api/
│   ├── routes/
│   │   ├── cases.py
│   │   ├── documents.py
│   │   ├── payments.py          # NEW
│   │   ├── consents.py          # NEW
│   │   ├── checklists.py        # NEW
│   │   ├── results.py           # NEW
│   │   └── integrations/
│   │       ├── max_webhook.py
│   │       ├── crm_taganay.py   # NEW
│   │       └── sheets.py        # NEW
│   └── schemas/
├── models/
│   ├── case_status.py           # + B2C финансовые статусы
│   ├── client.py                # NEW
│   ├── order.py                 # NEW
│   ├── payment.py               # NEW
│   ├── checklist.py             # NEW
│   ├── consent.py               # NEW
│   └── result_evidence.py       # NEW
├── core/
│   ├── audit_ils.py
│   ├── case_store.py
│   ├── success_fee.py           # NEW формулы SF
│   └── notifications.py         # NEW
├── integrations/
│   ├── max/
│   ├── crm_taganay/             # NEW
│   └── google_sheets/           # NEW
└── security/
```

Документы ТЗ: [b2c-monetization-tz.md](b2c-monetization-tz.md).

## 2. Доменные сущности

| Сущность | Назначение |
|----------|------------|
| `Client` | Физлицо / представитель |
| `Case` | Пенсионное дело |
| `Document` | Файл в Storage |
| `AuditFinding` | Расхождение ИЛС/трудовой |
| `Checklist` / `ChecklistItem` | Индивидуальный чек-лист |
| `ServicePackage` | DIAG / ACCOMP |
| `Order` | Заказ услуги |
| `Payment` | Платёж и фискализация |
| `ResultEvidence` | Доказательство результата |
| `Consent` | Согласие на ПДн |
| `Communication` | Уведомления и журнал |
| `ContractAcceptance` | Акцепт оферты + заказ |

Связь с CRM: `cases.crm_external_id` + `cases.id` (= `case_id`).

## 3. Черновик схемы PostgreSQL (Supabase)

```sql
-- roles implied: anon, authenticated, service_role
-- RLS enabled on all public tables

create table public.clients (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id),
  full_name text not null,
  phone text,
  email text,
  created_at timestamptz not null default now()
);

create table public.cases (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id),
  crm_external_id text,
  pipeline_status text not null default 'intake',
  b2c_status text not null default 'lead',
  first_contact_at timestamptz not null default now(),
  expert_user_id uuid,
  segment text,
  region_bucket text,
  problem_type text,
  created_at timestamptz not null default now()
);

create table public.consents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id),
  version text not null,
  accepted_at timestamptz not null default now(),
  ip inet,
  user_agent text
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id),
  storage_path text not null,
  doc_type text,
  uploaded_by uuid,
  created_at timestamptz not null default now()
);

create table public.checklist_items (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id),
  title text not null,
  item_type text not null,
  owner text not null,
  due_at timestamptz,
  status text not null default 'open',
  note text,
  sort_order int default 0
);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id),
  package_code text not null, -- DIAG | ACCOMP | SF_LUMP | SF_MONTH
  amount_rub numeric(12,2) not null,
  status text not null default 'pending',
  created_at timestamptz not null default now()
);

create table public.payments (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id),
  provider text,
  provider_payment_id text,
  status text not null,
  fiscal_status text,
  paid_at timestamptz
);

create table public.result_evidence (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id),
  monthly_before_rub numeric(12,2),
  monthly_after_rub numeric(12,2),
  lump_sum_rub numeric(12,2),
  result_effective_at date,
  confirmed_by uuid,
  confirmed_at timestamptz,
  document_id uuid references public.documents(id)
);

create table public.communications (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id),
  channel text not null,
  template_code text,
  sent_at timestamptz not null default now(),
  payload jsonb
);

create table public.access_audit (
  id bigserial primary key,
  actor_id uuid,
  case_id uuid,
  action text not null,
  at timestamptz not null default now()
);
```

Storage bucket: `pension-docs` (private). Пути вида `{case_id}/{document_id}/...`.

Миграция: [`supabase/migrations/20260722122128_b2c_schema_rls.sql`](../supabase/migrations/20260722122128_b2c_schema_rls.sql).

Применение на linked cloud-проект:

```powershell
npx supabase link --project-ref YOUR_REF
npx supabase db push
```

## 4. RLS (принципы)

1. Включить RLS на всех таблицах в `public`.
2. Клиент (`authenticated`): `client_id` / `case.client_id` = текущий пользователь.
3. Эксперт: доступ только к `cases.expert_user_id = auth.uid()`.
4. `service_role` — только backend (webhooks, CRM, OCR), **не** в браузере.
5. Views с `security_invoker` при необходимости.
6. Не использовать `user_metadata` для авторизации.

Пример:

```sql
alter table public.cases enable row level security;

create policy cases_select_own on public.cases
  for select to authenticated
  using (
    client_id in (select id from public.clients where user_id = auth.uid())
    or expert_user_id = auth.uid()
  );
```

## 5. Интеграции

### 5.1. CRM Taganay ([login](https://taganay.clientbase.ru/login.php))

- Создание/обновление лида и сделки при смене `b2c_status`.
- Поле связи: `case_id` (UUID SFRFR).
- Этапы CRM зеркалят финансовые статусы journey.
- ПДн-контакты живут в CRM; файлы дел — только в SFRFR Storage.

### 5.2. Google Sheets

- Односторонняя выгрузка whitelist-полей (см. journey).
- Service account; без экспорта Storage URL.
- При ошибке синка — retry, дело не блокируется.

### 5.3. Платежи

- Провайдер (ЮKassa / аналог) + webhook → `payments`.
- Фискализация чека для самозанятого/ИП — по выбранному провайдеру.

## 6. Расчёт success fee (модуль)

```python
# core/success_fee.py (целевой контракт)
SF_LUMP_RATE = 0.10
SF_MONTH_RATE = 0.50
SF_MONTHS = 3

def calc_success_fee(*, lump_sum_rub: float = 0, monthly_increase_rub: float = 0) -> dict:
    sf_lump = round(lump_sum_rub * SF_LUMP_RATE, 2) if lump_sum_rub > 0 else 0
    sf_month = round(monthly_increase_rub * SF_MONTHS * SF_MONTH_RATE, 2) if monthly_increase_rub > 0 else 0
    return {"sf_lump": sf_lump, "sf_month": sf_month, "sf_total": round(sf_lump + sf_month, 2)}
```

Счёт выставляется не раньше `result_effective_at + 60 days` (окно 2–3 месяца — настраиваемый параметр 60–90).

## 7. Расширение статусов кода

В `CaseStatus` / отдельном `B2CStatus` добавить значения из [b2c-customer-journey.md](b2c-customer-journey.md) §2.2, не ломая существующий `PIPELINE_ORDER`.
