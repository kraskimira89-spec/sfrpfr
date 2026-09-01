-- Очередь ingest — внутренний контур worker-а, не Data API для клиентов.

drop policy if exists document_ingest_jobs_select on public.document_ingest_jobs;
drop policy if exists document_ingest_jobs_insert on public.document_ingest_jobs;
drop policy if exists document_ingest_jobs_update on public.document_ingest_jobs;

revoke all on table public.document_ingest_jobs from public;
revoke all on table public.document_ingest_jobs from anon;
revoke all on table public.document_ingest_jobs from authenticated;
