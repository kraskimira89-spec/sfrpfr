-- Ступень 11: орган-ответчик и вид ответа (несколько входящих, не только СФР).

alter table public.case_response_reviews
  add column if not exists respondent text;

alter table public.case_response_reviews
  add column if not exists response_kind text;

do $$
begin
  alter table public.case_response_reviews
    add constraint case_response_reviews_respondent_check
    check (
      respondent is null
      or respondent in ('sfr', 'employer', 'archive', 'court', 'mfc', 'other')
    );
exception when duplicate_object then
  null;
end $$;

do $$
begin
  alter table public.case_response_reviews
    add constraint case_response_reviews_response_kind_check
    check (
      response_kind is null
      or response_kind in (
        'decision', 'request_docs', 'clarification', 'refusal', 'other'
      )
    );
exception when duplicate_object then
  null;
end $$;

-- Старые строки: по умолчанию СФР / решение (если пусто).
update public.case_response_reviews
set respondent = 'sfr'
where respondent is null;

update public.case_response_reviews
set response_kind = 'decision'
where response_kind is null;

comment on column public.case_response_reviews.respondent is
  'Орган/источник ответа: sfr|employer|archive|court|mfc|other';
comment on column public.case_response_reviews.response_kind is
  'Вид: decision|request_docs|clarification|refusal|other';
