select
  payment_id,
  order_id,
  provider,
  status,
  fiscal_status,
  paid_at
from {{ source('analytics_source', 'payments') }}
