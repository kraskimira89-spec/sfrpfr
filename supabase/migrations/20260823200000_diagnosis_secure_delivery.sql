-- ТЗ-28: безопасная выдача PDF диагностики + очередь уведомлений (draft → approve).

create table if not exists public.diagnostic_results (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  document_id uuid references public.documents (id) on delete set null,
  status text not null default 'draft'
    check (status in ('draft', 'reviewed', 'published', 'revoked')),
  version int not null default 1,
  checksum text,
  reviewed_by uuid,
  published_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists diagnostic_results_case_idx
  on public.diagnostic_results (case_id, created_at desc);

create unique index if not exists diagnostic_results_one_published_per_case
  on public.diagnostic_results (case_id)
  where status = 'published';

create table if not exists public.secure_share_links (
  id uuid primary key default gen_random_uuid(),
  diagnostic_result_id uuid not null references public.diagnostic_results (id) on delete cascade,
  case_id uuid not null references public.cases (id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  max_views int not null default 20,
  view_count int not null default 0,
  viewed_at timestamptz,
  revoked_at timestamptz,
  channel text
    check (channel is null or channel in ('email', 'max', 'cabinet')),
  created_at timestamptz not null default now()
);

create index if not exists secure_share_links_case_idx
  on public.secure_share_links (case_id);

create table if not exists public.notification_jobs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  diagnostic_result_id uuid references public.diagnostic_results (id) on delete set null,
  job_type text not null
    check (
      job_type in (
        'result_ready',
        'result_unread',
        'feedback_clarity',
        'feedback_step'
      )
    ),
  channel text not null check (channel in ('email', 'max')),
  template_version text not null default 'v1',
  subject text,
  body text not null,
  secure_share_link_id uuid references public.secure_share_links (id) on delete set null,
  scheduled_at timestamptz not null default now(),
  status text not null default 'draft'
    check (
      status in (
        'draft',
        'approved',
        'sent',
        'delivered',
        'failed',
        'cancelled',
        'skipped'
      )
    ),
  requires_staff_approval boolean not null default true,
  approved_by uuid,
  sent_at timestamptz,
  provider_message_id text,
  failure_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists notification_jobs_case_status_idx
  on public.notification_jobs (case_id, status);

create index if not exists notification_jobs_due_draft_idx
  on public.notification_jobs (scheduled_at)
  where status = 'draft';

comment on table public.diagnostic_results is
  'Опубликованный PDF диагностики; не слать файлом в email/MAX (ТЗ-28)';
comment on table public.secure_share_links is
  'Одноразовые/короткоживущие ссылки; в БД только token_hash (ТЗ-28)';
comment on table public.notification_jobs is
  'Очередь сервисных уведомлений: draft → approve → sent (ТЗ-28)';

alter table public.diagnostic_results enable row level security;
alter table public.secure_share_links enable row level security;
alter table public.notification_jobs enable row level security;
