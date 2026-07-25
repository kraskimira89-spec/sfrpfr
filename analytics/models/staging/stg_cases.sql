select
  case_id,
  segment,
  region_bucket,
  pipeline_status,
  b2c_status,
  problem_type,
  created_at,
  first_contact_at,
  preferred_channel,
  max_linked,
  web_linked
from {{ source('analytics_source', 'cases') }}
