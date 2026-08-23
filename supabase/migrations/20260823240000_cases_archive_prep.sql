-- Архивная подготовка: операционные поля без ПДн (playbook-archive-request-prep)
alter table public.cases
  add column if not exists archive_prep_status text,
  add column if not exists archive_tariff text,
  add column if not exists archive_successor text,
  add column if not exists archive_target text,
  add column if not exists archive_followup_at timestamptz;

alter table public.cases
  drop constraint if exists cases_archive_prep_status_check;

alter table public.cases
  add constraint cases_archive_prep_status_check
  check (
    archive_prep_status is null
    or archive_prep_status in (
      'diagnosis_ready',
      'period_collected',
      'route_agreed',
      'request_drafted',
      'client_review',
      'pack_issued',
      'awaiting_archive',
      'archive_reply',
      'next_step',
      'closed'
    )
  );

alter table public.cases
  drop constraint if exists cases_archive_tariff_check;

alter table public.cases
  add constraint cases_archive_tariff_check
  check (
    archive_tariff is null
    or archive_tariff in ('5000', '8000')
  );

comment on column public.cases.archive_prep_status is 'Статус подготовки архивного комплекта';
comment on column public.cases.archive_tariff is '5000 подготовка / 8000 до подачи';
comment on column public.cases.archive_successor is 'известен / неизвестен / проверить';
comment on column public.cases.archive_target is 'предполагаемый / подтверждённый';
comment on column public.cases.archive_followup_at is 'Контрольная дата ответа архива';
