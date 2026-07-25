-- Analytics mart tables are owned by analytics_transformer (created by dbt).
-- ENABLE ROW LEVEL SECURITY must run as that owner; see post-hooks in
-- analytics/dbt_project.yml. This migration only documents the contract.

comment on schema analytics is
  'Витрины dbt. RLS включается post-hook владельца analytics_transformer; '
  'политик для anon/authenticated нет. Схема не в Data API.';
