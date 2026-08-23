-- ТЗ-30: машина состояний выдачи PDF + idempotency + queued.

-- diagnostic_result: published ≠ sent; sent ≠ opened
alter table public.diagnostic_results
  drop constraint if exists diagnostic_results_status_check;

alter table public.diagnostic_results
  add constraint diagnostic_results_status_check
  check (
    status in (
      'draft',
      'reviewed',
      'published',
      'delivered',
      'opened',
      'feedback_pending',
      'feedback_received',
      'closed',
      'revoked'
    )
  );

-- notification_job: +queued; idempotency_key
alter table public.notification_jobs
  drop constraint if exists notification_jobs_status_check;

alter table public.notification_jobs
  add constraint notification_jobs_status_check
  check (
    status in (
      'draft',
      'approved',
      'queued',
      'sent',
      'delivered',
      'failed',
      'cancelled',
      'skipped'
    )
  );

alter table public.notification_jobs
  add column if not exists idempotency_key text;

create unique index if not exists notification_jobs_idempotency_uidx
  on public.notification_jobs (idempotency_key)
  where idempotency_key is not null;

-- Короче лимит просмотров по канону ТЗ (новые ссылки)
alter table public.secure_share_links
  alter column max_views set default 3;

alter table public.survey_campaigns
  add column if not exists idempotency_key text;

create unique index if not exists survey_campaigns_idempotency_uidx
  on public.survey_campaigns (idempotency_key)
  where idempotency_key is not null;

comment on column public.notification_jobs.idempotency_key is
  'result:{id}:notification:result_ready|result_unread:v1 — дедуп обработчиков';
comment on constraint diagnostic_results_status_check on public.diagnostic_results is
  'published ≠ sent ≠ opened (ТЗ-30)';
