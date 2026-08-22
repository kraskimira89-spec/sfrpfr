-- Операционные поля счетов. status pending/paid не меняем — ЮKassa и кабинеты.
alter table public.orders
  add column if not exists invoice_number text,
  add column if not exists due_at timestamptz,
  add column if not exists invoice_status text,
  add column if not exists pay_url text,
  add column if not exists sent_channel text,
  add column if not exists sent_at timestamptz,
  add column if not exists cancel_reason text,
  add column if not exists reminder_draft text,
  add column if not exists service_label text,
  add column if not exists next_action text;

comment on column public.orders.invoice_number is 'Человеческий номер счёта СЧ-…';
comment on column public.orders.due_at is 'Срок оплаты';
comment on column public.orders.invoice_status is 'Операционный статус счёта (draft/sent/overdue/…)';
comment on column public.orders.pay_url is 'Последняя ссылка на оплату';
comment on column public.orders.service_label is 'Название услуги как на /tarify/, без кодов SF';

update public.orders
set invoice_number = 'СЧ-' || upper(right(replace(id::text, '-', ''), 8))
where invoice_number is null;

update public.orders
set invoice_status = case
  when status = 'paid' then 'paid'
  when status in ('cancelled', 'canceled') then 'cancelled'
  when status in ('refund', 'refunded') then 'refund'
  when status = 'draft' then 'draft'
  else 'pending_payment'
end
where invoice_status is null;

update public.orders
set due_at = created_at + interval '3 days'
where due_at is null and status = 'pending';

create unique index if not exists orders_invoice_number_uidx
  on public.orders (invoice_number)
  where invoice_number is not null;

create index if not exists orders_due_at_idx
  on public.orders (due_at)
  where due_at is not null and status = 'pending';

create table if not exists public.finance_audit (
  id bigserial primary key,
  order_id uuid references public.orders (id) on delete restrict,
  case_id uuid,
  actor_id uuid,
  action text not null,
  payload jsonb not null default '{}'::jsonb,
  at timestamptz not null default now()
);

create index if not exists finance_audit_order_idx
  on public.finance_audit (order_id, at desc);

comment on table public.finance_audit is 'Неизменяемый журнал счетов; удаление через UI запрещено';

alter table public.finance_audit enable row level security;

revoke update, delete on public.finance_audit from anon, authenticated;
grant select, insert on public.finance_audit to authenticated;
