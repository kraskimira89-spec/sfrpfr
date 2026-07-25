select distinct
  coalesce(segment, 'unknown') as segment,
  coalesce(region_bucket, 'unknown') as region_bucket,
  coalesce(problem_type, 'unknown') as problem_type,
  preferred_channel
from {{ ref('fct_case_funnel') }}
