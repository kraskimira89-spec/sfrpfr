-- Черновик схемы tracker_sync (inbox/outbox/state/history).
-- Не включает webhook endpoint и не включает TRACKER_CASE_SYNC.
-- public.case_tracker_issues (STAZH) не трогаем.
-- public.tracker_sync_outbox (срез 1) остаётся до переноса в tracker_sync.outbox.
-- FK на cases(id) — осознанно отложен: политика удаления дел ещё не зафиксирована для bindings.
-- Apply на prod — только после отдельного согласования (SFRFR-118).

create schema if not exists tracker_sync;

comment on schema tracker_sync is
  'Синхронизация диспетчерских карточек Яндекс Трекера. Без ПДн. Отдельно от case_tracker_issues (STAZH).';

-- ---------------------------------------------------------------------------
-- bindings: case_root | work_item
-- ---------------------------------------------------------------------------
create table if not exists tracker_sync.bindings (
  id uuid primary key default gen_random_uuid(),
  organization_id text not null,
  tracker_issue_id text not null,
  tracker_issue_key text not null,
  case_id uuid not null,
  binding_kind text not null
    check (binding_kind in ('case_root', 'work_item')),
  purpose_key text not null,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, tracker_issue_id),
  unique (case_id, binding_kind, purpose_key)
);

create unique index if not exists bindings_issue_key_uq
  on tracker_sync.bindings (organization_id, tracker_issue_key);

create index if not exists bindings_case_idx
  on tracker_sync.bindings (case_id);

comment on table tracker_sync.bindings is
  'Связь дела с задачей Трекера (корень дела или work_item). purpose_key стабилен для идемпотентного create.';

-- ---------------------------------------------------------------------------
-- task_state: текущая проекция (не история)
-- ---------------------------------------------------------------------------
create table if not exists tracker_sync.task_state (
  binding_id uuid primary key
    references tracker_sync.bindings (id),
  tracker_status_key text,
  tracker_version bigint,
  tracker_updated_at timestamptz,
  app_stage_id text
    check (
      app_stage_id is null
      or app_stage_id in (
        'contact_consents',
        'documents',
        'precheck_summary',
        'analysis_payment',
        'full_analysis',
        'appeals_consent',
        'appeals_payment',
        'appeals_documents',
        'submission',
        'follow_up',
        'response_review',
        'escalation_package',
        'closure'
      )
    ),
  app_revision bigint not null default 0,
  local_revision bigint not null default 0,
  last_observed_at timestamptz,
  last_synced_at timestamptz,
  projected_fields jsonb not null default '{}'::jsonb
    check (jsonb_typeof(projected_fields) = 'object'),
  updated_at timestamptz not null default now()
);

create index if not exists task_state_status_idx
  on tracker_sync.task_state (tracker_status_key, binding_id);

create index if not exists task_state_stage_idx
  on tracker_sync.task_state (app_stage_id, binding_id);

comment on column tracker_sync.task_state.app_revision is
  'Ревизия фактов дела в приложении; не сравнивать с tracker_version.';
comment on column tracker_sync.task_state.tracker_version is
  'version объекта задачи в Tracker API.';
comment on column tracker_sync.task_state.local_revision is
  'Локальный счётчик применений sync на binding.';

-- ---------------------------------------------------------------------------
-- inbox
-- ---------------------------------------------------------------------------
create table if not exists tracker_sync.inbox (
  id uuid primary key default gen_random_uuid(),
  organization_id text not null,
  tracker_issue_id text not null,
  binding_id uuid references tracker_sync.bindings (id),
  event_kind text not null,
  source_event_id text,
  source_version bigint,
  dedupe_key text not null,
  payload_hash text not null,
  payload jsonb not null
    check (jsonb_typeof(payload) = 'object'),
  state text not null default 'pending'
    check (
      state in (
        'pending',
        'processing',
        'retry',
        'processed',
        'ignored',
        'rejected',
        'dead'
      )
    ),
  attempts integer not null default 0 check (attempts >= 0),
  available_at timestamptz not null default now(),
  lease_token uuid,
  lease_until timestamptz,
  received_at timestamptz not null default now(),
  last_received_at timestamptz not null default now(),
  duplicate_count integer not null default 0,
  finished_at timestamptz,
  last_error_code text,
  unique (organization_id, dedupe_key),
  check (
    state <> 'processing'
    or (lease_token is not null and lease_until is not null)
  )
);

create index if not exists inbox_ready_idx
  on tracker_sync.inbox (available_at, received_at)
  where state in ('pending', 'retry');

create index if not exists inbox_expired_lease_idx
  on tracker_sync.inbox (lease_until)
  where state = 'processing';

comment on table tracker_sync.inbox is
  'Входящие webhook/сигналы. Минимальный envelope без Authorization и ПДн.';

-- ---------------------------------------------------------------------------
-- change_history (append-only для runtime)
-- ---------------------------------------------------------------------------
create table if not exists tracker_sync.change_history (
  id uuid primary key default gen_random_uuid(),
  binding_id uuid not null
    references tracker_sync.bindings (id),
  local_revision bigint not null,
  source text not null
    check (
      source in ('tracker', 'application', 'reconciliation', 'operator')
    ),
  inbox_id uuid references tracker_sync.inbox (id),
  correlation_id uuid not null,
  tracker_version bigint,
  app_revision bigint,
  before_state jsonb not null,
  after_state jsonb not null,
  actor_ref text,
  reason_code text not null,
  recorded_at timestamptz not null default now(),
  source_occurred_at timestamptz,
  unique (binding_id, local_revision)
);

create index if not exists history_binding_time_idx
  on tracker_sync.change_history (binding_id, recorded_at desc);

comment on table tracker_sync.change_history is
  'Append-only история sync. Runtime-роль не должна иметь UPDATE/DELETE.';

-- ---------------------------------------------------------------------------
-- outbox (целевой; срез 1 живёт в public.tracker_sync_outbox)
-- ---------------------------------------------------------------------------
create table if not exists tracker_sync.outbox (
  id uuid primary key default gen_random_uuid(),
  binding_id uuid not null
    references tracker_sync.bindings (id),
  operation_kind text not null
    check (
      operation_kind in ('project_fields', 'transition', 'create_work_item')
    ),
  aggregate_revision bigint not null,
  idempotency_key text not null unique,
  correlation_id uuid not null,
  payload jsonb not null
    check (jsonb_typeof(payload) = 'object'),
  state text not null default 'pending'
    check (
      state in (
        'pending',
        'processing',
        'retry',
        'uncertain',
        'reconciling',
        'succeeded',
        'superseded',
        'dead'
      )
    ),
  attempts integer not null default 0,
  available_at timestamptz not null default now(),
  lease_token uuid,
  lease_until timestamptz,
  created_at timestamptz not null default now(),
  finished_at timestamptz,
  last_error_code text
);

create index if not exists outbox_ready_idx
  on tracker_sync.outbox (available_at, created_at)
  where state in ('pending', 'retry', 'uncertain');

comment on table tracker_sync.outbox is
  'Исходящие операции к Tracker API. uncertain = сверка, не слепой retry.';

-- ---------------------------------------------------------------------------
-- delivery_attempts
-- ---------------------------------------------------------------------------
create table if not exists tracker_sync.delivery_attempts (
  id uuid primary key default gen_random_uuid(),
  inbox_id uuid references tracker_sync.inbox (id),
  outbox_id uuid references tracker_sync.outbox (id),
  attempt_no integer not null,
  lease_token uuid not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  outcome text
    check (
      outcome is null
      or outcome in (
        'success',
        'retryable',
        'rejected',
        'unknown',
        'lease_lost'
      )
    ),
  http_status integer,
  error_code text,
  remote_request_id text,
  check (num_nonnulls(inbox_id, outbox_id) = 1)
);

create unique index if not exists attempt_inbox_no_uq
  on tracker_sync.delivery_attempts (inbox_id, attempt_no)
  where inbox_id is not null;

create unique index if not exists attempt_outbox_no_uq
  on tracker_sync.delivery_attempts (outbox_id, attempt_no)
  where outbox_id is not null;

-- ---------------------------------------------------------------------------
-- Privileges: только service_role (как case_chat_outbox / tracker_sync_outbox)
-- ---------------------------------------------------------------------------
revoke all on schema tracker_sync from public, anon, authenticated;
grant usage on schema tracker_sync to service_role;

revoke all on all tables in schema tracker_sync from public, anon, authenticated;
grant all on all tables in schema tracker_sync to service_role;

alter default privileges in schema tracker_sync
  revoke all on tables from public, anon, authenticated;

alter default privileges in schema tracker_sync
  grant all on tables to service_role;
