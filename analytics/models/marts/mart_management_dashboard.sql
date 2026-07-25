select
  created_month,
  coalesce(segment, 'unknown') as segment,
  coalesce(region_bucket, 'unknown') as region_bucket,
  coalesce(problem_type, 'unknown') as problem_type,
  preferred_channel,
  count(*) as cases_total,
  count(*) filter (where diagnostic_paid) as diagnostic_paid_cases,
  count(*) filter (where service_paid) as service_paid_cases,
  count(*) filter (where result_confirmed) as result_confirmed_cases,
  count(*) filter (where success_fee_due) as success_fee_due_cases,
  count(*) filter (where success_fee_paid) as success_fee_paid_cases,
  count(*) filter (where silent_180_days) as silent_180_days_cases,
  avg(days_to_result) filter (where result_confirmed) as avg_days_to_result
from {{ ref('fct_case_funnel') }}
group by 1, 2, 3, 4, 5
