-- После lock_document_ingest_jobs очередь недоступна клиентам (REVOKE).
-- PostgREST/service_role воркера нужен явный GRANT, иначе PGRST205 в schema cache.
grant select, insert, update, delete on public.document_ingest_jobs to service_role;
grant select, insert, update on public.document_groups to service_role;
