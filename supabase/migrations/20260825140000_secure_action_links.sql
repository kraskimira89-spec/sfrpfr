-- Sprint 1 MAX-first: generic secure action links (consent/upload/view/pay).
-- Не трогает secure_share_links / diag-share (ТЗ-28) — отдельная таблица.
-- Доступ: RLS включён без политик для anon/authenticated → фактически service-role only
-- (как diagnostic_results / secure_share_links). Клиентский JWT напрямую не читает.

create table if not exists public.secure_action_links (
  id uuid primary key default gen_random_uuid(),
  token_hash text not null unique,
  token_prefix text not null,
  purpose text not null
    check (
      purpose in (
        'consent',
        'upload',
        'view_pdf',
        'pay',
        'diag_share'
      )
    ),
  status text not null default 'active'
    check (
      status in (
        'active',
        'consumed',
        'revoked',
        'superseded'
      )
    ),
  case_id uuid not null references public.cases (id) on delete cascade,
  resource_id uuid,
  resource_type text
    check (
      resource_type is null
      or resource_type in (
        'order',
        'document',
        'diagnostic_result'
      )
    ),
  max_user_id text,
  max_uses int not null default 1 check (max_uses >= 1),
  use_count int not null default 0 check (use_count >= 0),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  consumed_at timestamptz,
  superseded_by uuid references public.secure_action_links (id) on delete set null,
  issued_via text not null default 'system'
    check (
      issued_via in (
        'system',
        'staff',
        'bot',
        'max'
      )
    ),
  created_by text,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint secure_action_links_use_lte_max check (use_count <= max_uses)
);

create index if not exists secure_action_links_case_purpose_idx
  on public.secure_action_links (case_id, purpose, created_at desc);

create index if not exists secure_action_links_status_expires_idx
  on public.secure_action_links (status, expires_at)
  where status = 'active';

create index if not exists secure_action_links_token_prefix_idx
  on public.secure_action_links (token_prefix);

create table if not exists public.secure_action_events (
  id uuid primary key default gen_random_uuid(),
  link_id uuid not null references public.secure_action_links (id) on delete cascade,
  case_id uuid not null references public.cases (id) on delete cascade,
  event_type text not null
    check (
      event_type in (
        'created',
        'verified',
        'consumed',
        'revoked',
        'superseded',
        'denied'
      )
    ),
  actor text,
  -- Без ПДн: channel, reason, purpose, user_agent_class — не СНИЛС/ФИО/email
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists secure_action_events_link_idx
  on public.secure_action_events (link_id, created_at desc);

create index if not exists secure_action_events_case_idx
  on public.secure_action_events (case_id, created_at desc);

alter table public.secure_action_links enable row level security;
alter table public.secure_action_events enable row level security;

grant select, insert, update on public.secure_action_links to service_role;
grant select, insert on public.secure_action_events to service_role;

comment on table public.secure_action_links is
  'Generic secure action tokens (MAX-first Sprint 1); в БД только token_hash, не raw. Отдельно от secure_share_links.';
comment on table public.secure_action_events is
  'Audit secure action links; metadata без ПДн.';
comment on column public.secure_action_links.token_hash is
  'HMAC-SHA256(raw, pepper); raw только в URL один раз.';
comment on column public.secure_action_links.token_prefix is
  'Короткий префикс raw для логов (не секрет целиком).';
