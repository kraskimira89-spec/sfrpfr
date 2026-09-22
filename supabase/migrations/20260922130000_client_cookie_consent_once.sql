-- Cookie-согласие вместе с ПДн (кнопка «Начать» в MAX = один раз).
-- Timestamp 20260922130000: не пересекаться с 20260922120000_case_reactivation_touches.
alter table public.clients
  add column if not exists cookie_consent_version text,
  add column if not exists cookie_consent_accepted_at timestamptz;

create index if not exists clients_cookie_consent_accepted_idx
  on public.clients (cookie_consent_accepted_at)
  where cookie_consent_accepted_at is not null;

comment on column public.clients.cookie_consent_version is
  'Версия согласия на cookies; фиксируется вместе с ПДн при «Начать» в MAX';
comment on column public.clients.cookie_consent_accepted_at is
  'Когда клиент принял cookies (тот же момент, что и ПДн)';
