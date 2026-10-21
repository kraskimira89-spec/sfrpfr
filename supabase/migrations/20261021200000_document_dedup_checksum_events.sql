-- Exact-dupe registry + upload events (SHA-256 до OCR).
-- Исторические дубли в documents не удаляем — только реестр для новых загрузок.

create table if not exists public.case_document_checksums (
  case_id uuid not null references public.cases (id) on delete cascade,
  checksum_sha256 text not null,
  size_bytes bigint not null default 0,
  document_id uuid not null references public.documents (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (case_id, checksum_sha256)
);

create index if not exists case_document_checksums_document_idx
  on public.case_document_checksums (document_id);

create table if not exists public.document_upload_events (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases (id) on delete cascade,
  document_id uuid not null references public.documents (id) on delete cascade,
  event_id text,
  attachment_id text,
  filename text,
  created_at timestamptz not null default now()
);

create unique index if not exists document_upload_events_case_event_uidx
  on public.document_upload_events (case_id, event_id)
  where event_id is not null;

create unique index if not exists document_upload_events_case_attach_uidx
  on public.document_upload_events (case_id, attachment_id)
  where attachment_id is not null;

create index if not exists document_upload_events_document_idx
  on public.document_upload_events (document_id);

-- Backfill: oldest document per (case_id, checksum) → registry (без mass-delete).
insert into public.case_document_checksums (case_id, checksum_sha256, size_bytes, document_id)
select distinct on (d.case_id, d.checksum_sha256)
  d.case_id,
  d.checksum_sha256,
  coalesce(d.size_bytes, 0),
  d.id
from public.documents d
where d.checksum_sha256 is not null
  and length(trim(d.checksum_sha256)) > 0
order by d.case_id, d.checksum_sha256, d.created_at asc nulls last
on conflict (case_id, checksum_sha256) do nothing;
