-- ТЗ-27: обратная связь после PDF-диагностики (без ПДн в аналитике).
create table if not exists public.diagnosis_feedback (
  case_id uuid primary key references public.cases (id) on delete cascade,
  pdf_issued_at timestamptz,
  pdf_opened_at timestamptz,
  feedback_status text not null default 'none'
    check (
      feedback_status in (
        'none',
        'nav_pending',
        'nav_sent',
        'understood',
        'need_help',
        'has_question',
        'survey_done',
        'do_not_disturb'
      )
    ),
  clarity_score smallint check (clarity_score is null or clarity_score between 1 and 4),
  expectation_match text
    check (expectation_match is null or expectation_match in ('yes', 'partial', 'no')),
  useful_section text
    check (
      useful_section is null
      or useful_section in ('periods', 'missing_docs', 'action_plan', 'ils_explain', 'other')
    ),
  improvement_comment text,
  first_plan_step_status text
    check (
      first_plan_step_status is null
      or first_plan_step_status in ('done', 'blocked', 'deferred')
    ),
  difficulty_category text
    check (
      difficulty_category is null
      or difficulty_category in ('ils', 'labor', 'archive', 'sfr', 'docs', 'other')
    ),
  follow_up_service_requested boolean,
  review_publication_consent text not null default 'none'
    check (
      review_publication_consent in ('none', 'requested', 'granted', 'denied')
    ),
  review_consent_version text,
  review_consent_at timestamptz,
  touch2_due_at timestamptz,
  touch3_due_at timestamptz,
  touch2_sent_at timestamptz,
  touch3_sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.diagnosis_feedback is
  'Сервисная обратная связь после выдачи PDF диагностики (ТЗ-27); без СНИЛС/паспорта в полях';

create index if not exists diagnosis_feedback_status_idx
  on public.diagnosis_feedback (feedback_status);

create index if not exists diagnosis_feedback_touch2_due_idx
  on public.diagnosis_feedback (touch2_due_at)
  where touch2_sent_at is null and feedback_status not in ('do_not_disturb', 'understood', 'survey_done');

alter table public.diagnosis_feedback enable row level security;
