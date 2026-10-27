-- Ступень 11: разбор ответа СФР (не путать с result_evidence = суммы пенсии).

create table if not exists public.case_response_reviews (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  document_id uuid not null references public.documents (id) on delete restrict,
  submission_report_id uuid references public.case_submission_reports (id) on delete set null,
  actor_id uuid,
  doc_date date,
  doc_number text,
  received_at timestamptz,
  source text check (
    source is null or source in ('cabinet', 'chat', 'mail', 'staff')
  ),
  completeness text not null default 'unknown'
    check (completeness in ('all_pages', 'need_more_pages', 'unknown')),
  status text not null default 'received'
    check (status in ('received', 'reviewing', 'reviewed')),
  deadline_quote text,
  deadline_quote_source text,
  deadline_quote_page text,
  ai_draft_md text,
  staff_draft_md text,
  reviewed_at timestamptz,
  sent_at timestamptz,
  sent_channel text check (
    sent_channel is null or sent_channel in ('email', 'yadisk', 'chat')
  ),
  outcome text check (
    outcome is null
    or outcome in ('need_docs', 'offer_escalation', 'close', 'wait_client')
  ),
  outcome_at timestamptz,
  outcome_actor_id uuid,
  idempotency_key text not null,
  constraint case_response_reviews_idempotency_key_uidx unique (idempotency_key)
);

create index if not exists case_response_reviews_case_created_idx
  on public.case_response_reviews (case_id, created_at desc);

alter table public.case_response_reviews enable row level security;

create policy case_response_reviews_staff_select on public.case_response_reviews
  for select using (private.is_staff());

do $$
begin
  execute $pol$
    create policy case_response_reviews_client_select on public.case_response_reviews
      for select using (private.can_access_case(case_id))
  $pol$;
exception when duplicate_object then
  null;
end $$;

grant select on public.case_response_reviews to authenticated;
grant all on public.case_response_reviews to service_role;

comment on table public.case_response_reviews is
  'Ступень 11: метаданные ответа СФР + AI/staff разбор; новый ответ = новая строка';
