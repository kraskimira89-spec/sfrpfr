select
  case_id,
  channel,
  communication_count,
  last_sent_at
from {{ source('analytics_source', 'communications_agg') }}
