-- Lint 0029: SECURITY DEFINER helpers must not live in PostgREST-exposed `public`.
-- RLS policies keep working (expressions bind by OID); /rest/v1/rpc/* stops exposing them.
-- Pattern already used for private.is_staff.

alter function public.is_case_client(uuid) set schema private;
alter function public.is_case_representative(uuid) set schema private;
alter function public.is_case_staff(uuid) set schema private;
alter function public.can_access_case(uuid) set schema private;

create or replace function private.is_case_client(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.cases c
    join public.clients cl on cl.id = c.client_id
    where c.id = p_case_id
      and cl.user_id = (select auth.uid())
  );
$$;

create or replace function private.is_case_representative(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.case_representatives cr
    where cr.case_id = p_case_id
      and cr.user_id = (select auth.uid())
  );
$$;

create or replace function private.is_case_staff(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select private.is_staff('operator')
      or exists (
        select 1
        from public.cases c
        where c.id = p_case_id
          and c.expert_user_id = (select auth.uid())
      );
$$;

create or replace function private.can_access_case(p_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select private.is_case_client(p_case_id)
      or private.is_case_representative(p_case_id)
      or private.is_case_staff(p_case_id);
$$;

grant usage on schema private to authenticated, service_role;

revoke all on function private.is_case_client(uuid) from public;
revoke all on function private.is_case_representative(uuid) from public;
revoke all on function private.is_case_staff(uuid) from public;
revoke all on function private.can_access_case(uuid) from public;

revoke execute on function private.is_case_client(uuid) from anon;
revoke execute on function private.is_case_representative(uuid) from anon;
revoke execute on function private.is_case_staff(uuid) from anon;
revoke execute on function private.can_access_case(uuid) from anon;

grant execute on function private.is_case_client(uuid) to authenticated, service_role;
grant execute on function private.is_case_representative(uuid) to authenticated, service_role;
grant execute on function private.is_case_staff(uuid) to authenticated, service_role;
grant execute on function private.can_access_case(uuid) to authenticated, service_role;

-- Optional thin wrappers removed: do not recreate in public (would re-open /rpc).
-- New policies must call private.can_access_case / private.is_case_*.
