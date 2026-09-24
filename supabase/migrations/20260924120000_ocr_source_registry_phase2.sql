-- Phase 2: реестр источников OCR (local/Disk paths + audit).
-- Не заполняет старые строки; Storage fallback остаётся включённым на VPS.

alter table public.documents
  add column if not exists size_bytes bigint,
  add column if not exists document_version integer not null default 1,
  add column if not exists local_path text,
  add column if not exists local_status text,
  add column if not exists yandex_disk_path text,
  add column if not exists yandex_disk_status text,
  add column if not exists primary_ocr_source text,
  add column if not exists ocr_source_used text,
  add column if not exists ocr_source_verified_at timestamptz;

alter table public.document_ingest_jobs
  add column if not exists ocr_source_used text,
  add column if not exists bytes_sha256 text,
  add column if not exists resolve_trace jsonb;

comment on column public.documents.local_path is
  'Относительный путь от storage_local_path (uploads_root), без leading slash';
comment on column public.documents.local_status is
  'quarantine | verified | missing | corrupt (app-level)';
comment on column public.documents.yandex_disk_path is
  'Полный API path disk:/SFRFR-cases/... после успешного mirror';
comment on column public.document_ingest_jobs.resolve_trace is
  'JSON array безопасных кодов попыток resolve; без путей/ФИО/текста/hash';
