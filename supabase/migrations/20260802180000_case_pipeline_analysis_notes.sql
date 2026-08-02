-- Обоснование DeepSeek (после детерминированной сверки) для кабинета эксперта.
alter table public.case_pipeline_data
  add column if not exists analysis_notes text;

comment on column public.case_pipeline_data.analysis_notes is
  'Обезличенное юридическое обоснование findings (DeepSeek); не для клиента без HITL';
