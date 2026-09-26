-- ТЗ-35 A3: доказательство согласия ПДн — кто дал, в каком канале, на какой текст.
-- Все новые колонки nullable: старые согласия остаются действующими.
alter table public.consents
  add column if not exists client_id uuid references public.clients (id) on delete set null,
  add column if not exists max_user_id text,
  add column if not exists text_sha256 text,
  add column if not exists source text,
  add column if not exists evidence jsonb not null default '{}'::jsonb;

alter table public.consents
  drop constraint if exists consents_text_sha256_format;
alter table public.consents
  add constraint consents_text_sha256_format
  check (text_sha256 is null or text_sha256 ~ '^[0-9a-f]{64}$');

create index if not exists consents_case_id_idx on public.consents (case_id);
create index if not exists consents_client_id_idx
  on public.consents (client_id)
  where client_id is not null;

comment on column public.consents.client_id is 'Клиент, давший согласие (ТЗ-35 §5)';
comment on column public.consents.max_user_id is 'Идентификатор пользователя MAX, нажавшего «Начать»';
comment on column public.consents.text_sha256 is 'SHA-256 показанного текста согласия (hex)';
comment on column public.consents.source is 'max_start | inherited | cabinet | cookies';
comment on column public.consents.evidence is 'Технические сведения события: update_type, callback_id, chat_id';
