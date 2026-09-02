-- Allow acquaint (code) alongside quality / review_request (ТЗ-29).
alter table public.survey_campaigns
  drop constraint if exists survey_campaigns_survey_type_check;

alter table public.survey_campaigns
  add constraint survey_campaigns_survey_type_check
  check (
    survey_type in (
      'clarity',
      'first_step',
      'quality',
      'review_request',
      'acquaint'
    )
  );

comment on constraint survey_campaigns_survey_type_check on public.survey_campaigns is
  'ТЗ-29: clarity/first_step/quality/review_request + acquaint (ознакомление)';

-- first_plan_step: pending до ответа first_step (код выставляет pending после clarity=clear)
alter table public.diagnosis_feedback
  drop constraint if exists diagnosis_feedback_first_plan_step_status_check;

alter table public.diagnosis_feedback
  add constraint diagnosis_feedback_first_plan_step_status_check
  check (
    first_plan_step_status is null
    or first_plan_step_status in ('pending', 'done', 'blocked', 'deferred')
  );