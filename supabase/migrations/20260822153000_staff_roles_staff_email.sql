-- Рабочий email сотрудника без обхода auth.users через list_users (GoTrue list_users может падать).
alter table public.staff_roles
  add column if not exists staff_email text;

create unique index if not exists staff_roles_staff_email_lower_uidx
  on public.staff_roles (lower(staff_email))
  where staff_email is not null;
