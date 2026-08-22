-- Следующий шаг и кто должен действовать (кабинет сотрудника).
alter table public.cases
  add column if not exists next_action text,
  add column if not exists next_action_at timestamptz,
  add column if not exists waiting_on text;

alter table public.cases
  drop constraint if exists cases_waiting_on_check;

alter table public.cases
  add constraint cases_waiting_on_check
  check (
    waiting_on is null
    or waiting_on in ('staff', 'client', 'archive', 'sfr', 'payment', 'none')
  );

comment on column public.cases.next_action is 'Следующий шаг сотрудника по делу';
comment on column public.cases.next_action_at is 'Срок следующего шага';
comment on column public.cases.waiting_on is 'staff/client/archive/sfr/payment/none';

create index if not exists cases_next_action_at_idx
  on public.cases (next_action_at)
  where next_action_at is not null;

create index if not exists cases_waiting_on_idx
  on public.cases (waiting_on)
  where waiting_on is not null;
