select
  p.payment_id,
  o.order_id,
  o.case_id,
  o.package_code,
  o.amount_band,
  o.status as order_status,
  p.provider,
  p.status as payment_status,
  p.fiscal_status,
  p.paid_at,
  date_trunc('month', coalesce(p.paid_at, o.created_at))::date as payment_month
from {{ ref('stg_payments') }} p
join {{ ref('stg_orders') }} o on o.order_id = p.order_id
