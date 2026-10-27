-- Ступень 10: журнал контроля рассмотрения (дата = cases.next_action_at, не параллельное поле).

create table if not exists public.case_follow_up_events (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  created_at timestamptz not null default now(),
  actor_id uuid,
  kind text not null check (
    kind in ('assign_control', 'check', 'reschedule', 'response_handoff')
  ),
  check_result text check (
    check_result is null
    or check_result in ('no_response', 'need_more_info', 'client_reported_response')
  ),
  control_at timestamptz,
  previous_control_at timestamptz,
  next_action_text text,
  reason text,
  waiting_on text,
  expert_user_id uuid,
  document_id uuid references public.documents (id) on delete set null,
  idempotency_key text not null,
  constraint case_follow_up_events_idempotency_key_uidx unique (idempotency_key)
);

create index if not exists case_follow_up_events_case_created_idx
  on public.case_follow_up_events (case_id, created_at desc);

alter table public.case_follow_up_events enable row level security;

create policy case_follow_up_events_staff_select on public.case_follow_up_events
  for select using (private.is_staff());

do $$
begin
  execute $pol$
    create policy case_follow_up_events_client_select on public.case_follow_up_events
      for select using (private.can_access_case(case_id))
  $pol$;
exception when duplicate_object then
  null;
end $$;

grant select on public.case_follow_up_events to authenticated;
grant all on public.case_follow_up_events to service_role;

comment on table public.case_follow_up_events is
  'Ступень 10: назначения/проверки/переносы контроля; контрольная дата хранится в cases.next_action_at';
