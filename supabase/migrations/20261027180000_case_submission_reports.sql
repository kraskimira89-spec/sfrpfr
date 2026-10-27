-- Этап 9: структурированный отчёт о подаче (форма клиента/сотрудника).
-- access_audit остаётся для derive funnel; поля формы — здесь.

create table if not exists public.case_submission_reports (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  created_at timestamptz not null default now(),
  actor_id uuid,
  actor_kind text not null check (actor_kind in ('client', 'staff')),
  kind text not null check (kind in ('client_reported', 'help_requested', 'receipt_verified')),
  submitted_on date,
  method text check (method is null or method in ('gosuslugi', 'sfr', 'mfc', 'post', 'other')),
  submitted_what text,
  appeal_number text,
  proof_document_id uuid references public.documents (id) on delete set null,
  comment text,
  source text check (source is null or source in ('client_self', 'client_words')),
  package_version text,
  idempotency_key text not null,
  constraint case_submission_reports_idempotency_key_uidx unique (idempotency_key)
);

create index if not exists case_submission_reports_case_created_idx
  on public.case_submission_reports (case_id, created_at desc);

alter table public.case_submission_reports enable row level security;

create policy case_submission_reports_staff_select on public.case_submission_reports
  for select using (private.is_staff());

do $$
begin
  execute $pol$
    create policy case_submission_reports_client_select on public.case_submission_reports
      for select using (private.can_access_case(case_id))
  $pol$;
exception when duplicate_object then
  null;
end $$;

grant select on public.case_submission_reports to authenticated;
grant all on public.case_submission_reports to service_role;

comment on table public.case_submission_reports is
  'Этап 9: сообщения о подаче / помощи / проверке расписки; история без удаления';
