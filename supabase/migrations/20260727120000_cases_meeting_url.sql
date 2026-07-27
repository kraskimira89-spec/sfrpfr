-- ТЗ-14: ссылка на встречу Телемост в карточке дела
alter table public.cases
  add column if not exists meeting_url text;

comment on column public.cases.meeting_url is 'URL видеовстречи (Яндекс Телемост), ТЗ-14';
