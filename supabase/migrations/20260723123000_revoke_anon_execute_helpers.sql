-- Revoke anon/public EXECUTE on SECURITY DEFINER helpers (Data API RPC).

revoke execute on function public.is_case_client(uuid) from anon, public;
revoke execute on function public.is_case_representative(uuid) from anon, public;
revoke execute on function public.is_case_staff(uuid) from anon, public;
revoke execute on function public.can_access_case(uuid) from anon, public;
revoke execute on function private.is_staff(text) from anon, public;

do $$
begin
  if to_regprocedure('public.is_case_expert(uuid)') is not null then
    execute 'revoke execute on function public.is_case_expert(uuid) from anon, public';
    execute 'grant execute on function public.is_case_expert(uuid) to authenticated';
  end if;
end $$;

grant execute on function public.is_case_client(uuid) to authenticated;
grant execute on function public.is_case_representative(uuid) to authenticated;
grant execute on function public.is_case_staff(uuid) to authenticated;
grant execute on function public.can_access_case(uuid) to authenticated;
grant execute on function private.is_staff(text) to authenticated;
