-- MVP: внутренние задачи Яндекс Трекер (очередь STAZH) без ПДн
create table if not exists public.case_tracker_issues (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  case_ref text not null,
  issue_type text not null,
  direction text,
  source text,
  priority text,
  tracker_issue_key text not null,
  tracker_issue_url text,
  tracker_sync_status text not null default 'ok',
  tracker_sync_error text,
  is_open boolean not null default true,
  created_by uuid,
  created_at timestamptz not null default now(),
  payload_snapshot jsonb not null default '{}'::jsonb,
  constraint case_tracker_issues_type_chk check (
    issue_type in (
      'bug',
      'sla_incident',
      'channel_conflict',
      'process_improvement',
      'development',
      'content',
      'security_privacy',
      'analytics_hypothesis',
      'partner_request'
    )
  )
);

comment on table public.case_tracker_issues is
  'Связь дела SFRFR с обезличенной задачей Яндекс Трекер (STAZH). Без ПДн.';

comment on column public.case_tracker_issues.case_ref is
  'sha256(case_id+salt)[:12] — псевдоним для Трекера';

create index if not exists case_tracker_issues_case_id_idx
  on public.case_tracker_issues (case_id);

create index if not exists case_tracker_issues_case_ref_idx
  on public.case_tracker_issues (case_ref);

create unique index if not exists case_tracker_issues_open_dedup_uidx
  on public.case_tracker_issues (case_ref, issue_type)
  where is_open = true and tracker_sync_status = 'ok';

alter table public.cases
  add column if not exists tracker_last_issue_key text;

comment on column public.cases.tracker_last_issue_key is
  'Последний ключ задачи Трекер (STAZH-…), без ПДн';
