select
  case_id,
  created_month,
  segment,
  region_bucket,
  problem_type,
  b2c_status,
  preferred_channel,
  max_linked,
  web_linked,
  silent_180_days
from {{ ref('fct_case_funnel') }}
where silent_180_days
