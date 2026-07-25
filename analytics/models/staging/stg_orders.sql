select
  order_id,
  case_id,
  package_code,
  amount_band,
  status,
  created_at
from {{ source('analytics_source', 'orders') }}
