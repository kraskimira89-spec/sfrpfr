-- Нуджи оплаты из чата: связка «бот предложил → клиент оплатил» (без ПДн).
create table if not exists public.case_payment_nudges (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  order_id uuid not null references public.orders (id) on delete cascade,
  message_id uuid references public.case_messages (id) on delete set null,
  channel text not null default 'unified',
  source text not null default 'chat_bot',
  created_at timestamptz not null default now(),
  converted_at timestamptz,
  converted_payment_id uuid references public.payments (id) on delete set null
);

create index if not exists case_payment_nudges_case_order_idx
  on public.case_payment_nudges (case_id, order_id, created_at desc);

create index if not exists case_payment_nudges_open_order_idx
  on public.case_payment_nudges (order_id)
  where converted_at is null;

alter table public.case_payment_nudges enable row level security;

create policy case_payment_nudges_staff_select on public.case_payment_nudges
  for select using (private.is_staff());

grant select on public.case_payment_nudges to authenticated;
