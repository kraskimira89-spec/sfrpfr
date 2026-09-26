-- ТЗ-35 B1: анкета нового клиента в MAX (§6). Все колонки nullable — старые записи не трогаем.
alter table public.clients
  add column if not exists last_name text,
  add column if not exists first_name text,
  add column if not exists middle_name text,
  add column if not exists birth_year smallint;

alter table public.clients
  drop constraint if exists clients_birth_year_range;
alter table public.clients
  add constraint clients_birth_year_range
  check (birth_year is null or birth_year between 1900 and 2100);

alter table public.cases
  add column if not exists experience_bucket text,
  add column if not exists problem_text text,
  add column if not exists questionnaire_completed_at timestamptz;

alter table public.cases
  drop constraint if exists cases_experience_bucket_values;
alter table public.cases
  add constraint cases_experience_bucket_values
  check (experience_bucket is null or experience_bucket in ('lt5', '5_10', '10_20', 'gt20', 'unknown'));

alter table public.cases
  drop constraint if exists cases_problem_text_len;
alter table public.cases
  add constraint cases_problem_text_len
  check (problem_text is null or char_length(problem_text) <= 2000);

comment on column public.clients.last_name is 'Фамилия из анкеты MAX (ТЗ-35 §6)';
comment on column public.clients.first_name is 'Имя из анкеты MAX';
comment on column public.clients.middle_name is 'Отчество из анкеты MAX (может отсутствовать)';
comment on column public.clients.birth_year is 'Год рождения из анкеты MAX';
comment on column public.cases.experience_bucket is 'Ориентировочный стаж: lt5 | 5_10 | 10_20 | gt20 | unknown';
comment on column public.cases.problem_text is 'Краткое описание проблемы из анкеты (до 2000 символов)';
comment on column public.cases.questionnaire_completed_at is 'Когда клиент завершил анкету в MAX';
