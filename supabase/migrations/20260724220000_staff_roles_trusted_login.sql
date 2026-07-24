-- Доверенный MAX сотрудника: после первого одобрения руководителя повторный вход без него
alter table public.staff_roles
  add column if not exists trusted_login_max_user_id text,
  add column if not exists trusted_login_at timestamptz;

create index if not exists staff_roles_trusted_login_max_user_id_idx
  on public.staff_roles (trusted_login_max_user_id)
  where trusted_login_max_user_id is not null;
