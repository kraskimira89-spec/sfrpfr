set -u
cd /opt/sfrfr-supabase/supabase/docker
q() { sudo docker compose exec -T db psql -U postgres -Atc "$1" </dev/null; }
q "select rolname, rolsuper from pg_roles where rolname in ('postgres','supabase_admin')"
q "select datname, pg_size_pretty(pg_database_size(datname)), (select count(*) from pg_stat_activity a where a.datname=d.datname) from pg_database d where not datistemplate"
q "select version()"
id
sudo docker compose exec -T db sh -c 'which pg_dump pg_dumpall pg_restore; pg_dump --version' </dev/null
sudo bash -c '. /etc/sfrfr-backup.env
export RCLONE_CONFIG_YC_TYPE=s3 RCLONE_CONFIG_YC_PROVIDER=Other RCLONE_CONFIG_YC_ENDPOINT="$S3_ENDPOINT" RCLONE_CONFIG_YC_REGION="$S3_REGION" RCLONE_CONFIG_YC_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" RCLONE_CONFIG_YC_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY"
rclone lsf "yc:$S3_BUCKET" 2>&1 | tail -3; echo lsf_rc=${PIPESTATUS[0]}'
