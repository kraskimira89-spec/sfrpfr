-- Согласие на ПДн один раз на клиента (MAX и кабинет).
alter table public.clients
  add column if not exists pdn_consent_version text,
  add column if not exists pdn_consent_accepted_at timestamptz;

create index if not exists clients_pdn_consent_accepted_idx
  on public.clients (pdn_consent_accepted_at)
  where pdn_consent_accepted_at is not null;

comment on column public.clients.pdn_consent_version is
  'Версия согласия ПДн; один раз на клиента, без повторных запросов';
comment on column public.clients.pdn_consent_accepted_at is
  'Когда клиент принял согласие ПДн (MAX «Начать» или кабинет)';
