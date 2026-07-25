with order_flags as (
  select
    case_id,
    bool_or(package_code = 'DIAG' and status = 'paid') as diagnostic_paid,
    bool_or(package_code = 'ACCOMP' and status = 'paid') as service_paid,
    bool_or(package_code in ('SF_LUMP', 'SF_MONTH')) as success_fee_due,
    bool_or(package_code in ('SF_LUMP', 'SF_MONTH') and status = 'paid') as success_fee_paid
  from {{ ref('stg_orders') }}
  group by case_id
),
latest_result as (
  select distinct on (case_id)
    case_id,
    monthly_increase_band,
    lump_sum_band,
    result_effective_at,
    confirmed_at,
    result_confirmed
  from {{ ref('stg_result_evidence') }}
  order by case_id, confirmed_at desc nulls last, result_effective_at desc nulls last, evidence_id desc
)
select
  c.case_id,
  date_trunc('month', c.created_at)::date as created_month,
  c.segment,
  c.region_bucket,
  c.problem_type,
  c.b2c_status,
  c.pipeline_status,
  c.preferred_channel,
  c.max_linked,
  c.web_linked,
  coalesce(o.diagnostic_paid, false) as diagnostic_paid,
  coalesce(o.service_paid, false) as service_paid,
  coalesce(r.result_confirmed, false) as result_confirmed,
  coalesce(r.monthly_increase_band, 'unknown') as monthly_increase_band,
  coalesce(r.lump_sum_band, 'unknown') as lump_sum_band,
  coalesce(o.success_fee_due, false) as success_fee_due,
  coalesce(o.success_fee_paid, false) as success_fee_paid,
  case
    when r.confirmed_at is not null then (r.confirmed_at::date - c.created_at::date)
  end as days_to_result,
  (
    c.b2c_status = 'client_silent_escalation'
    and c.created_at <= now() - interval '180 days'
  ) as silent_180_days
from {{ ref('stg_cases') }} c
left join order_flags o on o.case_id = c.case_id
left join latest_result r on r.case_id = c.case_id
