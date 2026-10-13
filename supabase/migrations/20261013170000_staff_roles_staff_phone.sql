-- Телефон сотрудника для входа admin через MAX (phone → trusted_max).
alter table public.staff_roles
  add column if not exists staff_phone text;

create unique index if not exists staff_roles_staff_phone_uidx
  on public.staff_roles (staff_phone)
  where staff_phone is not null;

-- Известный владелец/специалист: MAX 6407832 ↔ +79091950408 (ТЗ-25).
update public.staff_roles
set staff_phone = '+79091950408'
where staff_phone is null
  and (
    trusted_login_max_user_id = '6407832'
    or max_user_id = '6407832'
  );
