-- Маркетинговое согласие (отдельно от ПДн и сервисных сообщений по обращению).
-- История не удаляется: grant / deny / revoke остаются как события.

create table if not exists public.marketing_consents (
  id uuid primary key default gen_random_uuid(),
  contact_key text not null,
  -- max:<user_id> | email:<normalized> | client:<uuid>
  channel text not null check (channel in ('max', 'email', 'sms')),
  status text not null check (status in ('granted', 'denied', 'revoked')),
  consent_text_version text not null default 'marketing-max-v1',
  source text not null check (
    source in (
      'website_form',
      'max_bot_button',
      'double_opt_in',
      'admin',
      'stop_command'
    )
  ),
  proof_id text,
  case_id uuid references public.cases (id) on delete set null,
  client_id uuid references public.clients (id) on delete set null,
  actor_id text,
  suppression_reason text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists marketing_consents_contact_channel_created_idx
  on public.marketing_consents (contact_key, channel, created_at desc);

create index if not exists marketing_consents_client_id_idx
  on public.marketing_consents (client_id)
  where client_id is not null;

create index if not exists marketing_consents_case_id_idx
  on public.marketing_consents (case_id)
  where case_id is not null;

alter table public.marketing_consents enable row level security;

-- Staff/service role через API (service key); authenticated клиенты — только свой client_id.
create policy marketing_consents_select_own on public.marketing_consents
  for select to authenticated
  using (
    client_id is not null
    and client_id in (
      select c.id from public.clients c where c.user_id = auth.uid()
    )
  );

grant select on public.marketing_consents to authenticated;
-- insert/update только service role (API)
grant select, insert on public.marketing_consents to service_role;

comment on table public.marketing_consents is
  'Журнал marketing consent по каналу; ПДн-согласие и service messages — отдельно.';
