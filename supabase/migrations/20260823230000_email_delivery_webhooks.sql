-- ТЗ-31: webhook-доставка e-mail ≠ открытие PDF; delivery_events.

-- PDF: link_issued (ссылка выдана) ≠ email delivered
alter table public.diagnostic_results
  drop constraint if exists diagnostic_results_status_check;

alter table public.diagnostic_results
  add constraint diagnostic_results_status_check
  check (
    status in (
      'draft',
      'reviewed',
      'published',
      'link_issued',
      'delivered',
      'opened',
      'feedback_pending',
      'feedback_received',
      'closed',
      'revoked'
    )
  );

-- notification_jobs: статусы доставки письма + метаданные
alter table public.notification_jobs
  drop constraint if exists notification_jobs_status_check;

alter table public.notification_jobs
  add constraint notification_jobs_status_check
  check (
    status in (
      'draft',
      'approved',
      'queued',
      'accepted',
      'sent',
      'delivered',
      'deferred',
      'failed',
      'soft_bounce',
      'hard_bounce',
      'cancelled',
      'skipped'
    )
  );

alter table public.notification_jobs
  add column if not exists provider text;

alter table public.notification_jobs
  add column if not exists recipient_contact_key text;

alter table public.notification_jobs
  add column if not exists recipient_domain text;

alter table public.notification_jobs
  add column if not exists approved_at timestamptz;

alter table public.notification_jobs
  add column if not exists queued_at timestamptz;

alter table public.notification_jobs
  add column if not exists accepted_at timestamptz;

alter table public.notification_jobs
  add column if not exists delivered_at timestamptz;

alter table public.notification_jobs
  add column if not exists failed_at timestamptz;

alter table public.notification_jobs
  add column if not exists error_code text;

alter table public.notification_jobs
  add column if not exists error_category text;

alter table public.notification_jobs
  add column if not exists retry_count int not null default 0;

create unique index if not exists notification_jobs_provider_message_uidx
  on public.notification_jobs (provider_message_id)
  where provider_message_id is not null;

create table if not exists public.delivery_events (
  id uuid primary key default gen_random_uuid(),
  notification_job_id uuid references public.notification_jobs (id) on delete set null,
  provider text not null,
  provider_event_id text,
  provider_message_id text,
  event_type text not null,
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  severity text not null
    check (severity in ('info', 'warning', 'error')),
  error_code text,
  error_category text,
  event_fingerprint text not null unique,
  payload_redacted jsonb not null default '{}'::jsonb,
  unmatched boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists delivery_events_job_idx
  on public.delivery_events (notification_job_id, occurred_at desc);

create index if not exists delivery_events_type_idx
  on public.delivery_events (event_type, received_at desc);

create index if not exists delivery_events_unmatched_idx
  on public.delivery_events (received_at desc)
  where unmatched = true;

-- Техстоп по каналу (≠ отзыв согласия ПДн)
create table if not exists public.contact_delivery_status (
  contact_key text not null,
  channel text not null check (channel in ('email', 'max', 'sms')),
  status text not null
    check (
      status in (
        'active',
        'temporary_problem',
        'hard_bounce',
        'complained',
        'unsubscribed',
        'blocked'
      )
    ),
  reason text,
  updated_at timestamptz not null default now(),
  primary key (contact_key, channel)
);

comment on table public.delivery_events is
  'Нормализованные webhook-события доставки; без полного e-mail/PDF/ПДн (ТЗ-31)';
comment on table public.contact_delivery_status is
  'Техстоп канала; не путать с отзывом согласия ПДн (ТЗ-31)';

alter table public.delivery_events enable row level security;
alter table public.contact_delivery_status enable row level security;
