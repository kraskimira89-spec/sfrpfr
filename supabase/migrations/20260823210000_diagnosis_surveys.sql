-- ТЗ-29: сервисные опросы после PDF (MAX clarity MVP).

create table if not exists public.survey_campaigns (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  diagnostic_result_id uuid references public.diagnostic_results (id) on delete set null,
  survey_type text not null
    check (survey_type in ('clarity', 'first_step', 'quality', 'review_request')),
  channel text not null check (channel in ('max', 'email')),
  status text not null default 'draft'
    check (
      status in (
        'scheduled',
        'draft',
        'approved',
        'sent',
        'completed',
        'cancelled',
        'expired'
      )
    ),
  scheduled_at timestamptz not null default now(),
  sent_at timestamptz,
  completed_at timestamptz,
  expires_at timestamptz,
  staff_approved_by uuid,
  template_version text not null default 'survey-v1',
  body text,
  touch_index int not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists survey_campaigns_case_idx
  on public.survey_campaigns (case_id, survey_type, status);

create index if not exists survey_campaigns_due_idx
  on public.survey_campaigns (scheduled_at)
  where status in ('draft', 'scheduled');

create table if not exists public.survey_responses (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.survey_campaigns (id) on delete cascade,
  question_code text not null,
  answer_code text not null,
  comment text,
  channel text not null check (channel in ('max', 'email')),
  submitted_at timestamptz not null default now(),
  confirmation_method text,
  token_id uuid,
  unique (campaign_id, question_code)
);

create table if not exists public.survey_action_tokens (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.survey_campaigns (id) on delete cascade,
  token_hash text not null unique,
  answer_code text not null,
  used_at timestamptz,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists survey_action_tokens_campaign_idx
  on public.survey_action_tokens (campaign_id);

create table if not exists public.survey_suppressions (
  id uuid primary key default gen_random_uuid(),
  case_id uuid references public.cases (id) on delete cascade,
  contact_key text,
  reason text not null
    check (
      reason in (
        'do_not_contact',
        'pd_consent_revoked',
        'marketing_opt_out',
        'hard_bounce',
        'client_requested_stop'
      )
    ),
  source text,
  created_at timestamptz not null default now()
);

create index if not exists survey_suppressions_case_idx
  on public.survey_suppressions (case_id);

comment on table public.survey_campaigns is
  'Сервисные опросы после диагностики; draft→approve (ТЗ-29)';
comment on table public.survey_action_tokens is
  'Одноразовые callback-токены MAX/email; в payload только token (ТЗ-29)';

alter table public.survey_campaigns enable row level security;
alter table public.survey_responses enable row level security;
alter table public.survey_action_tokens enable row level security;
alter table public.survey_suppressions enable row level security;
