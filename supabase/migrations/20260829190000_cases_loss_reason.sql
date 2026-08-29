-- Причина отказа / закрытия сделки в кабинете сотрудника (вместо amo LOSS_REASON).
alter table public.cases
  add column if not exists loss_reason text;

alter table public.cases
  add column if not exists closed_at timestamptz;

comment on column public.cases.loss_reason is
  'Причина отказа (канон LOSS из sales playbook); null если закрыто успешно или ещё открыто';
comment on column public.cases.closed_at is
  'Когда дело закрыто (успех или отказ)';
