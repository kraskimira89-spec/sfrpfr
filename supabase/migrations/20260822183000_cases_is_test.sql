-- Тестовые дела не должны попадать в рабочую очередь по умолчанию.
alter table public.cases
  add column if not exists is_test boolean not null default false;

comment on column public.cases.is_test is 'Тестовая/служебная запись (AMO E2E и т.п.)';

create index if not exists cases_is_test_idx
  on public.cases (is_test)
  where is_test = true;

update public.cases c
set is_test = true
from public.clients cl
where c.client_id = cl.id
  and c.is_test = false
  and cl.full_name ~* '(тест|test|amo token|e2e|recheck)';
