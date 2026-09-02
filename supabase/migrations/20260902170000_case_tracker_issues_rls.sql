-- RLS for case_tracker_issues (writes via service_role / API only).
alter table public.case_tracker_issues enable row level security;

drop policy if exists case_tracker_issues_staff_select on public.case_tracker_issues;
create policy case_tracker_issues_staff_select on public.case_tracker_issues
  for select to authenticated
  using (private.can_access_case(case_id));

revoke all on table public.case_tracker_issues from anon;
grant select on table public.case_tracker_issues to authenticated;
grant all on table public.case_tracker_issues to service_role;
