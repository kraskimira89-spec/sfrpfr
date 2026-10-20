-- После cutover supabase2 Storage API (service_role) получает 403:
-- "permission denied for table buckets" — без SELECT на storage.buckets
-- upload в pension-docs падает, клиент MAX видит «пришлите ещё раз».
-- Канон: service_role обходит RLS объектов; buckets нужен для резолва bucket id.

grant usage on schema storage to service_role;
grant select on table storage.buckets to service_role;
grant all on table storage.objects to service_role;

-- На части сборок есть sequences у storage.*; игнор, если нет.
do $$
begin
  grant usage, select on all sequences in schema storage to service_role;
exception
  when undefined_table then null;
  when insufficient_privilege then null;
end $$;
