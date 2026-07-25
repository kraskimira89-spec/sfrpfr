select
  case_id,
  created_month,
  segment,
  region_bucket,
  problem_type,
  result_confirmed,
  success_fee_due,
  success_fee_paid,
  monthly_increase_band,
  lump_sum_band,
  days_to_result
from {{ ref('fct_case_funnel') }}
where success_fee_due
