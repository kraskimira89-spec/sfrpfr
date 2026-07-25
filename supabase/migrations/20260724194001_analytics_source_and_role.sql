-- Isolated analytics boundary: dbt may read only the whitelisted views below
-- and may create relations only in analytics. No PII, document paths, message
-- bodies/payloads, raw payment provider IDs, or raw monetary values are exposed.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'analytics_transformer') then
    create role analytics_transformer
      login
      noinherit
      nosuperuser
      nocreatedb
      nocreaterole
      noreplication
      nobypassrls
      password null;
  end if;
end
$$;

create schema if not exists analytics_source;
create schema if not exists analytics;

revoke all on schema analytics_source from public, anon, authenticated;
revoke all on schema analytics from public, anon, authenticated;
revoke all on schema public from analytics_transformer;
revoke all on all tables in schema public from analytics_transformer;
revoke all on all sequences in schema public from analytics_transformer;
revoke all on schema auth from analytics_transformer;
revoke all on schema storage from analytics_transformer;

-- These views are intentionally in a non-exposed schema. They run as their
-- owner so the analytics role never needs SELECT on public tables protected by
-- RLS. Their projection is the complete data contract for dbt.
create or replace view analytics_source.cases
with (security_barrier = true) as
select
  c.id as case_id,
  c.segment,
  c.region_bucket,
  c.pipeline_status,
  c.b2c_status,
  c.problem_type,
  c.created_at,
  c.first_contact_at,
  coalesce(cl.preferred_channel, 'unset') as preferred_channel,
  (cl.max_user_id is not null) as max_linked,
  (cl.user_id is not null) as web_linked
from public.cases c
join public.clients cl on cl.id = c.client_id;

create or replace view analytics_source.orders
with (security_barrier = true) as
select
  o.id as order_id,
  o.case_id,
  o.package_code,
  case
    when o.amount_rub <= 0 then '0'
    when o.amount_rub <= 5000 then '1–5 тыс.'
    when o.amount_rub <= 10000 then '5–10 тыс.'
    else '10+ тыс.'
  end as amount_band,
  o.status,
  o.created_at
from public.orders o;

create or replace view analytics_source.payments
with (security_barrier = true) as
select
  p.id as payment_id,
  p.order_id,
  p.provider,
  p.status,
  p.fiscal_status,
  p.paid_at
from public.payments p;

create or replace view analytics_source.result_evidence
with (security_barrier = true) as
select
  r.id as evidence_id,
  r.case_id,
  case
    when r.monthly_after_rub is null or r.monthly_before_rub is null then 'unknown'
    when r.monthly_after_rub <= r.monthly_before_rub then '0'
    when r.monthly_after_rub - r.monthly_before_rub <= 5000 then '1–5 тыс.'
    when r.monthly_after_rub - r.monthly_before_rub <= 10000 then '5–10 тыс.'
    else '10+ тыс.'
  end as monthly_increase_band,
  case
    when r.lump_sum_rub is null or r.lump_sum_rub <= 0 then '0'
    when r.lump_sum_rub <= 5000 then '1–5 тыс.'
    when r.lump_sum_rub <= 10000 then '5–10 тыс.'
    else '10+ тыс.'
  end as lump_sum_band,
  r.result_effective_at,
  r.confirmed_at,
  (r.confirmed_at is not null) as result_confirmed
from public.result_evidence r;

create or replace view analytics_source.communications_agg
with (security_barrier = true) as
select
  c.case_id,
  c.channel,
  count(*)::integer as communication_count,
  max(c.sent_at) as last_sent_at
from public.communications c
group by c.case_id, c.channel;

revoke all on all tables in schema analytics_source from public, anon, authenticated;
grant usage on schema analytics_source to analytics_transformer;
grant select on all tables in schema analytics_source to analytics_transformer;

grant usage, create on schema analytics to analytics_transformer;

comment on schema analytics_source is
  'Обезличенный read-only контракт для dbt: только whitelist аналитических полей.';
comment on schema analytics is
  'Витрины dbt. Владение и запись разрешены только роли analytics_transformer.';
