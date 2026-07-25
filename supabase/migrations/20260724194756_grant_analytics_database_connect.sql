-- Required for the separately authenticated dbt role. This does not grant
-- access to public tables, schemas, Storage, Auth, or service credentials.
grant connect on database postgres to analytics_transformer;
