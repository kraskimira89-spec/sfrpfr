select
  evidence_id,
  case_id,
  monthly_increase_band,
  lump_sum_band,
  result_effective_at,
  confirmed_at,
  result_confirmed
from {{ source('analytics_source', 'result_evidence') }}
