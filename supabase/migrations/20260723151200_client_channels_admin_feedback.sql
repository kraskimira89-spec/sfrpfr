-- Client channel parity (TZ-09) + admin knowledge feedback (TZ-04).

alter table public.clients
  add column if not exists max_user_id text,
  add column if not exists preferred_channel text
    not null default 'unset'
    check (preferred_channel in ('max_miniapp', 'web_cabinet', 'unset')),
  add column if not exists preferred_channel_set_at timestamptz;

create unique index if not exists clients_max_user_id_uidx
  on public.clients (max_user_id)
  where max_user_id is not null;

create table if not exists public.case_knowledge_feedback (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  author_user_id uuid references auth.users (id) on delete set null,
  what_worked text,
  documents_note text,
  sfr_outcome text,
  quality text not null check (quality in ('draft', 'verified', 'template', 'rejected')),
  created_at timestamptz not null default now()
);

create index if not exists case_knowledge_feedback_case_id_idx
  on public.case_knowledge_feedback (case_id, created_at desc);

alter table public.case_knowledge_feedback enable row level security;

drop policy if exists knowledge_feedback_select on public.case_knowledge_feedback;
create policy knowledge_feedback_select on public.case_knowledge_feedback
  for select to authenticated
  using (public.is_case_staff(case_id));

drop policy if exists knowledge_feedback_insert on public.case_knowledge_feedback;
create policy knowledge_feedback_insert on public.case_knowledge_feedback
  for insert to authenticated
  with check (
    public.is_case_staff(case_id)
    and author_user_id = (select auth.uid())
  );

grant select, insert on public.case_knowledge_feedback to authenticated;
