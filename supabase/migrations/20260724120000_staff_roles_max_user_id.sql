-- Привязка MAX руководителя/сотрудника для подтверждения входа в admin-кабинет
alter table public.staff_roles
  add column if not exists max_user_id text;

create unique index if not exists staff_roles_max_user_id_uidx
  on public.staff_roles (max_user_id)
  where max_user_id is not null;
